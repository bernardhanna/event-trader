import os
import time
import json
import re
import hashlib
import sqlite3
import feedparser

# set a custom user agent for feedparser
feedparser.USER_AGENT = "Mozilla/5.0 (compatible; EventTraderBot/1.0; +http://159.65.201.126)"

import requests
from datetime import datetime as dt
from decimal import Decimal, ROUND_DOWN
from dotenv import load_dotenv
from openai import OpenAI
import google.generativeai as genai
from trader_feeds import fetch_trader_news
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
CONF_THRESHOLD = 70  # lowered to 70
EURUSD_FX_RATE = 1.08

# Whitelisted Twitter handles
try:
    with open("whitelisted_accounts.json", "r") as f:
        WHITELISTED_ACCOUNTS = json.load(f)
except:
    WHITELISTED_ACCOUNTS = [
        "Bloomberg", "Reuters", "howardlindzon", "RampCapitalLLC",
        "charliebilello", "sentimenttrader", "KobeissiLetter",
        "KailashConcepts", "hhhypergrowth", "FinancialJuice",
        "AlmanackReport", "TheTranscript_"
    ]

# Feeds (100+ entries from major sources)
FEEDS = [
 "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/marketsNews",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.marketwatch.com/rss/marketpulse",
    "https://finance.yahoo.com/news/rssindex",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.ft.com/?format=rss",
    "https://www.investing.com/rss/news_285.rss",
    "https://www.investing.com/rss/news_25.rss",
    "https://www.bloomberg.com/feed/podcast/etf-report.xml",
    "https://www.bloomberg.com/feed/podcast/bloomberg-surveillance.xml",
    "https://www.benzinga.com/rss",
    "https://seekingalpha.com/feed.xml",
    "https://www.zerohedge.com/fullrss2.xml",
    "https://www.wsj.com/xml/rss/3_7031.xml",
    "https://www.fool.com/feeds/index.aspx",
    "https://www.valuewalk.com/feed/",
    "https://news.tradingeconomics.com/rss",
    "https://www.businessinsider.com/rss",
    "https://www.cnet.com/rss/news/",
    "https://www.theverge.com/rss/index.xml",
    "https://www.wired.com/feed/rss",
    "https://www.techcrunch.com/feed/",
    "https://arstechnica.com/feed/",
    "https://www.engadget.com/rss.xml",
    "https://venturebeat.com/feed/",
    "https://gizmodo.com/rss",
    "https://thenextweb.com/feed/",
    "https://www.androidcentral.com/rss.xml",
    "https://www.macrumors.com/macrumors.xml",
    "https://9to5mac.com/feed/",
    "https://www.reddit.com/r/technology/.rss",
    "https://oilprice.com/rss/main",
    "https://www.energyvoice.com/feed/",
    "https://www.rigzone.com/news/rss/",
    "https://www.worldoil.com/rss",
    "https://www.offshore-mag.com/rss",
    "https://feeds.reuters.com/reuters/worldNews",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.npr.org/rss/rss.php?id=1004",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://apnews.com/rss",
    "https://globalnews.ca/feed/",
    "https://www.dw.com/en/top-stories/s-9097?maca=en-rss-en-all-1573-rdf",
    "https://www.france24.com/en/rss",
    "https://english.alarabiya.net/.mrss/en/rss.xml",
    "https://www.abc.net.au/news/feed/51120/rss.xml",
    "https://www.politico.com/rss/politics08.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
    "https://www.realclearpolitics.com/index.xml",
    "https://thehill.com/rss/syndicator/19110",
    "https://www.cnn.com/rss/cnn_allpolitics.rss",
    "https://www.npr.org/rss/rss.php?id=1014",
    "https://www.usnews.com/rss/news",
    "https://www.nbcnews.com/politics/politics-news/rss.xml",
    "https://www.federalreserve.gov/feeds/press_all.xml",
    "https://www.oecd.org/newsroom/newsroom-rss.xml",
    "https://www.imf.org/en/News/Articles/rss",
    "https://www.bis.org/rss/rss.xml",
    "https://www.ecb.europa.eu/rss/press.html",
    "https://www.bankofengland.co.uk/rss/rss.xml",
    "https://www.bls.gov/feed/bls_latest.rss",
    "https://www.bea.gov/rss/newsreleases.xml",
    "https://www.tradingview.com/feed/",
    "https://www.forexlive.com/feed",
    "https://www.dailyfx.com/feeds/all",
    "https://www.fxstreet.com/rss/news",
    "https://asia.nikkei.com/rss/feed/nar",
    "https://www.scmp.com/rss/91/feed",
    "https://www.channelnewsasia.com/rssfeeds/8395986",
    "https://www.japantimes.co.jp/feed/",
    "https://thediplomat.com/feed/",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://cryptonews.com/news/feed",
    "https://news.bitcoin.com/feed/",
    "https://decrypt.co/feed",
    "https://blockworks.co/feed",
    "https://www.forbes.com/most-popular/feed/",
    "https://www.economist.com/finance-and-economics/rss.xml",
    "https://hbr.org/rss",
    "https://time.com/feed/",
    "https://www.fastcompany.com/rss",
    "https://qz.com/feed",
    "https://www.inc.com/rss.xml",
    "https://www.theatlantic.com/feed/all/",
    "https://www.newyorker.com/feed/news",
    "https://www.vox.com/rss/index.xml",
    "https://www.nasdaq.com/feed/rssoutbound",
    "https://www.wsj.com/xml/rss/3_7085.xml",
    "https://money.cnn.com/rss/magazines_fortune.xml",
    "https://www.cfr.org/rss.xml",
    "https://www.project-syndicate.org/feeds/rss"
]

# Prompt
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
  "event_type": "earnings/m&a/macro/regulation/natural_disaster/other",
  "sentiment": "positive/negative/neutral"
}
Return {} if no trade.
"""

# SQLite
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
        INSERT INTO events
        (id, headline, summary, confidence, direction, reason, event_type, sentiment, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        uid, headline, summary, confidence, direction, reason, event_type, sentiment, dt.utcnow().isoformat()
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
                if (dt.utcnow() - published_time).total_seconds() > 7200:
                    continue
                yield e.title, getattr(e, "summary", "")
        except Exception as e:
            print(f"Feed error: {e}")

def fetch_twitter():
    for account in WHITELISTED_ACCOUNTS:
        yield f"{account}: Breaking news"

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
            return {}
        match = re.search(r"\{.*?\}", content, re.DOTALL)
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
        if isinstance(item, tuple):
            title, summary = item
        else:
            title, summary = item, ""
        user_msg = f"HEADLINE: {title}\nSUMMARY: {summary}"
        evt = gpt_json(EVENT_PROMPT, user_msg)
        if not evt or evt.get("confidence", 0) < CONF_THRESHOLD:
            evt = gemini_json(f"{EVENT_PROMPT}\n\n{user_msg}")
        if not evt or evt.get("confidence", 0) < CONF_THRESHOLD:
            continue
        uid = sha(title)
        if seen(uid):
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
        time.sleep(600)