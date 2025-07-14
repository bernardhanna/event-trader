import os
import feedparser
import time
import json
import re
import hashlib
import sqlite3
import pytz
import requests
from datetime import datetime as dt
from decimal import Decimal, ROUND_DOWN
from dotenv import load_dotenv
from openai import OpenAI
import google.generativeai as genai
from trader_feeds import fetch_trader_news
from dateutil import parser
from dateutil.tz import gettz

try:
    import alpaca_trade_api as trade_api
except ImportError:
    trade_api = None

feedparser.USER_AGENT = "Mozilla/5.0 (compatible; EventTraderBot/1.0; +http://159.65.201.126)"

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash")
else:
    gemini_model = None

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
ALPACA_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
ALPACA_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
TRADE_ENABLED = bool(ALPACA_KEY and ALPACA_SECRET and trade_api)

if TRADE_ENABLED:
    alpaca = trade_api.REST(ALPACA_KEY, ALPACA_SECRET, base_url=ALPACA_URL)
else:
    alpaca = None

TOTAL_CAPITAL_EUR = 1000
MAX_POSITION_PCT = 0.05
CONF_THRESHOLD = 50
EURUSD_FX_RATE = 1.08
NEWS_MAX_AGE_HOURS = int(os.getenv("NEWS_MAX_AGE_HOURS", "12"))

try:
    with open("whitelisted_accounts.json", "r") as f:
        WHITELISTED_ACCOUNTS = json.load(f)
except:
    WHITELISTED_ACCOUNTS = []

try:
    with open("feeds.json", "r") as f:
        FEEDS = json.load(f)
except:
    FEEDS = []

EVENT_PROMPT = """
You are an aggressive event-driven trading analyst seeking asymmetric opportunities.
Given a HEADLINE and SUMMARY, identify even weak signals worth exploring.
Return only JSON with:
{
  "event": ...,
  "assets_affected": [tickers],
  "direction": "long" or "short",
  "confidence": 0-100,
  "reason": "...",
  "event_type": "earnings/m&a/macro/regulation/natural_disaster/other",
  "sentiment": "positive/negative/neutral"
}
Return {} only if completely irrelevant or spam.
"""

DB = sqlite3.connect("events.db", check_same_thread=False)
DB.execute("""
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    headline TEXT,
    summary TEXT,
    confidence INTEGER,
    direction TEXT,
    reason TEXT,
    event_type TEXT,
    sentiment TEXT,
    timestamp TEXT
)
""")
DB.commit()

def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()

def seen(uid):
    return DB.execute("SELECT 1 FROM events WHERE id=?", (uid,)).fetchone() is not None

def mark_event(uid, headline, summary, confidence, direction, reason, event_type, sentiment):
    DB.execute("""
        INSERT OR REPLACE INTO events
        (id, headline, summary, confidence, direction, reason, event_type, sentiment, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        uid, headline, summary, confidence, direction, reason, event_type, sentiment, dt.utcnow().isoformat()
    ))
    DB.commit()

def fetch_news():
    tzinfos = {
        "PDT": gettz("US/Pacific"),
        "PST": gettz("US/Pacific"),
        "EDT": gettz("US/Eastern"),
        "EST": gettz("US/Eastern"),
        "CDT": gettz("US/Central"),
        "CST": gettz("US/Central"),
        "MDT": gettz("US/Mountain"),
        "MST": gettz("US/Mountain")
    }
    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                uid = sha(e.title)
                if seen(uid):
                    continue
                if hasattr(e, "published"):
                    try:
                        published = parser.parse(e.published, tzinfos=tzinfos)
                        if published.tzinfo is None:
                            published = published.replace(tzinfo=pytz.UTC)
                    except Exception as ex:
                        print(f"[{url}] Date parse failed: {e.published} ({ex})")
                        continue
                    now = dt.utcnow().replace(tzinfo=pytz.UTC)
                    if (now - published).total_seconds() > NEWS_MAX_AGE_HOURS * 3600:
                        print(f"[{url}] Rejected due to age: {e.title}")
                        continue
                yield e.title, getattr(e, "summary", "")
        except Exception as e:
            print(f"[{url}] Feed error: {e}")

def fetch_twitter():
    if not TWITTER_BEARER_TOKEN or not WHITELISTED_ACCOUNTS:
        return
    headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
    session = requests.Session()
    try:
        resp = session.get(
            "https://api.twitter.com/2/users/by",
            params={"usernames": ",".join(WHITELISTED_ACCOUNTS)},
            headers=headers,
            timeout=10,
        )
        if not resp.ok:
            print(f"[Twitter] lookup error {resp.status_code}: {resp.text}")
            return
        users = resp.json().get("data", [])
    except Exception as ex:
        print(f"[Twitter] lookup failed: {ex}")
        return
    for user in users:
        uid = user.get("id")
        uname = user.get("username")
        if not uid:
            continue
        try:
            r = session.get(
                f"https://api.twitter.com/2/users/{uid}/tweets",
                params={"max_results": 5, "tweet.fields": "created_at"},
                headers=headers,
                timeout=10,
            )
            if r.status_code == 429:
                reset = int(r.headers.get("x-rate-limit-reset", time.time() + 60))
                wait = max(30, reset - int(time.time()))
                print(f"[Twitter] rate limited, sleeping {wait}s")
                time.sleep(wait)
                continue
            if not r.ok:
                print(f"[Twitter] tweets error {uname} {r.status_code}: {r.text}")
                continue
            for tw in r.json().get("data", []):
                text = tw.get("text", "").replace("\n", " ")
                yield f"{uname}: {text}", ""
        except Exception as ex:
            print(f"[Twitter] error for {uname}: {ex}")
        time.sleep(1)

def gpt_json(prompt, user_msg):
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.2
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print(f"GPT error: {e}")
        return {}

def gemini_json(prompt: str) -> dict:
    if not gemini_model:
        return {}
    try:
        response = gemini_model.generate_content(prompt)
        content = getattr(response, "text", None)
        if not content or not content.strip():
            return {}
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        print(f"Gemini error: {e}")
        return {}
    return {}

def pos_size(conf):
    w = (conf - CONF_THRESHOLD) / (100 - CONF_THRESHOLD)
    w = max(0, min(1, w))
    return round(TOTAL_CAPITAL_EUR * MAX_POSITION_PCT * (0.6 + 0.4 * w), 2)

def tg(msg):
    if TG_TOKEN and TG_CHAT:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                data={"chat_id": TG_CHAT, "text": msg, "parse_mode": "Markdown"},
                timeout=10
            )
            if not r.ok:
                print(f"Telegram error {r.status_code}: {r.text}")
        except Exception as e:
            print(f"Telegram error: {e}")
    else:
        print(msg)

def place_trade(ticker, direction, size_eur):
    if not alpaca:
        return False, None
    size_usd = size_eur * EURUSD_FX_RATE
    try:
        quote = alpaca.get_latest_quote(ticker)
        price = quote.ask_price if direction == "buy" else quote.bid_price
        if not price:
            return False, None
        qty = Decimal(size_usd / price).quantize(Decimal('1'), rounding=ROUND_DOWN)
        if qty <= 0:
            return False, None
        side = "sell" if direction == "short" else "buy"
        order = alpaca.submit_order(
            symbol=ticker,
            qty=float(qty),
            side=side,
            type="market",
            time_in_force="day"
        )
        return True, order.id
    except Exception as e:
        tg(f"Alpaca error: {e}")
        return False, None

def process():
    found = False
    sources = list(fetch_news()) + list(fetch_twitter()) + [(s["title"], s["summary"]) for s in fetch_trader_news()]
    for item in sources:
        title, summary = item if isinstance(item, tuple) else (item, "")
        user_msg = f"HEADLINE: {title}\nSUMMARY: {summary}"
        evt = gpt_json(EVENT_PROMPT, user_msg)
        if not evt or evt.get("confidence", 0) < CONF_THRESHOLD:
            print(f"Rejected by GPT or below threshold: {title}")
            evt = gemini_json(f"{EVENT_PROMPT}\n\n{user_msg}")
        if not evt or evt.get("confidence", 0) < CONF_THRESHOLD:
            print(f"Rejected by Gemini or below threshold: {title}")
            continue
        uid = sha(title)
        if seen(uid):
            print(f"Duplicate ignored: {title}")
            continue
        mark_event(
            uid, title, summary,
            evt['confidence'], evt['direction'], evt['reason'],
            evt.get("event_type", "other"), evt.get("sentiment", "neutral")
        )
        size = pos_size(evt['confidence'])
        msg = (
            f"🔥 *Event Signal* ({evt['confidence']}%)\n"
            f"*Headline:* {title}\n"
            f"*Type:* {evt.get('event_type', 'other')}\n"
            f"*Sentiment:* {evt.get('sentiment', 'neutral')}\n"
            f"*Direction:* {evt['direction']}\n"
            f"*Reason:* {evt['reason']}\n"
            f"*Size:* €{size}"
        )
        for asset in evt.get("assets_affected", []):
            msg += f"\n*Asset:* `{asset}`"
            if TRADE_ENABLED:
                success, oid = place_trade(asset, evt['direction'], size)
                msg += f"\nExec: {'✅' if success else '❌'}"
        tg(msg)
        found = True
    return found

if __name__ == "__main__":
    print("[EventTrader v0.9] running with Twitter + JSON whitelist + Gemini fallback")
    while True:
        found = process()
        if not found:
            tg("Heartbeat: no trades generated")
        time.sleep(600)