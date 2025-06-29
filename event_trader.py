# event_trader.py

import os
import time
import json
import hashlib
import sqlite3
import feedparser
import requests
from datetime import datetime as dt
from decimal import Decimal, ROUND_DOWN
from dotenv import load_dotenv
from openai import OpenAI
import google.generativeai as genai

try:
    import alpaca_trade_api as trade_api
except ImportError:
    trade_api = None

# Load .env
load_dotenv()

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash")
else:
    gemini_model = None

# OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Telegram
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")

# Alpaca
ALPACA_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
ALPACA_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

TRADE_ENABLED = bool(ALPACA_KEY and ALPACA_SECRET and trade_api)

if TRADE_ENABLED:
    alpaca = trade_api.REST(ALPACA_KEY, ALPACA_SECRET, base_url=ALPACA_URL)
else:
    alpaca = None

# Config
TOTAL_CAPITAL_EUR = 1000
MAX_POSITION_PCT = 0.05
CONF_THRESHOLD = 80
EURUSD_FX_RATE = 1.08

# Feeds
FEEDS = [
    "https://feeds.reuters.com/reuters/worldNews",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
]

# Event Prompt
EVENT_PROMPT = """
You are a professional event-driven trading analyst.
Given a HEADLINE and SUMMARY, decide if there is a trading opportunity.
Return JSON ONLY with:
{
  "event": ...,
  "assets_affected": [tickers],
  "direction": "long" or "short",
  "confidence": 0-100,
  "reason": "...",
  "event_type": "earnings/m&a/macro/regulation/natural_disaster/other"
}
Return {} if no trade.
"""

# DB
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
    timestamp TEXT
)
""")
DB.commit()

def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()

def seen(uid):
    return DB.execute("SELECT 1 FROM events WHERE id=?", (uid,)).fetchone() is not None

def mark_event(uid, headline, summary, confidence, direction, reason, event_type):
    DB.execute("""
        INSERT INTO events
        (id, headline, summary, confidence, direction, reason, event_type, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        uid, headline, summary, confidence, direction, reason, event_type, dt.utcnow().isoformat()
    ))
    DB.commit()

def fetch_news():
    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                uid = sha(e.title)
                if seen(uid):
                    continue
                published_time = dt.utcnow()
                if hasattr(e, "published_parsed") and e.published_parsed:
                    published_time = dt(*e.published_parsed[:6])
                if (dt.utcnow() - published_time).total_seconds() > 3600:
                    continue
                yield e.title, getattr(e, "summary", "")
        except Exception as e:
            print(f"Feed error: {e}")

def gpt_json(prompt, user_msg):
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
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
            print("Gemini returned empty content.")
            return {}
        print(f"Gemini raw content:\n{content[:200]}...")  # show only first 200 chars
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            print(f"Gemini returned invalid JSON:\n{content}")
            return {}
    except Exception as e:
        print(f"Gemini API/network error: {e}")
        return {}
    if not gemini_model:
        return {}
    try:
        response = gemini_model.generate_content(prompt)
        content = getattr(response, "text", None)
        if not content:
            return {}
        return json.loads(content)
    except Exception as e:
        print(f"Gemini error: {e}")
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
    for title, summary in fetch_news():
        user_msg = f"HEADLINE: {title}\nSUMMARY: {summary}"
        evt = gpt_json(EVENT_PROMPT, user_msg)
        if not evt or evt.get("confidence", 0) < CONF_THRESHOLD:
            evt = gemini_json(f"{EVENT_PROMPT}\n\n{user_msg}")
        if not evt or evt.get("confidence", 0) < CONF_THRESHOLD:
            continue
        uid = sha(title)
        if seen(uid):
            continue
        mark_event(uid, title, summary, evt['confidence'], evt['direction'], evt['reason'], evt.get("event_type", "other"))
        size = pos_size(evt['confidence'])
        msg = (
            f"🔥 *Event Signal* ({evt['confidence']}%)\n"
            f"*Headline:* {title}\n"
            f"*Type:* {evt.get('event_type', 'other')}\n"
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
    print("[EventTrader v0.6] running with event_type tagging")
    heartbeat_counter = 0
    while True:
        found = process()
        heartbeat_counter += 1
        if heartbeat_counter >= 6:
            if not found:
                tg("✅ *EventTrader heartbeat*: no signals found, system OK.")
            heartbeat_counter = 0
        time.sleep(600)
