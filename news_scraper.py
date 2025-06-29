import os, json, hashlib
import requests
import feedparser
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime
import sqlite3

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

DB = sqlite3.connect("events.db", check_same_thread=False)
DB.execute("""
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    headline TEXT,
    summary TEXT,
    timestamp TEXT,
    category TEXT,
    direction TEXT,
    confidence INTEGER,
    sentiment TEXT,
    reason TEXT,
    assets TEXT
)
""")
DB.commit()

def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()

def headline_seen(uid):
    return DB.execute("SELECT 1 FROM events WHERE id=?", (uid,)).fetchone() is not None

def mark(uid):
    DB.execute("INSERT OR REPLACE INTO events (id) VALUES (?)", (uid,))
    DB.commit()

def fetch_rss():
    feeds = [
        "https://feeds.reuters.com/reuters/worldNews",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.aljazeera.com/xml/rss/all.xml",
    ]
    for url in feeds:
        feed = feedparser.parse(url)
        for e in feed.entries:
            yield e.title, e.summary

def fetch_newsapi():
    try:
        url = f"https://newsapi.org/v2/top-headlines?language=en&pageSize=10&apiKey={NEWS_API_KEY}"
        data = requests.get(url).json()
        for article in data.get("articles", []):
            yield article.get("title", ""), article.get("description", "")
    except Exception as e:
        print(f"NewsAPI error: {e}")

def fetch_finnhub():
    try:
        url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
        data = requests.get(url).json()
        for item in data:
            yield item.get("headline", ""), item.get("summary", "")
    except Exception as e:
        print(f"Finnhub error: {e}")

def fetch_polygon():
    try:
        url = f"https://api.polygon.io/v2/reference/news?limit=10&apiKey={POLYGON_API_KEY}"
        data = requests.get(url).json()
        for item in data.get("results", []):
            yield item.get("title", ""), item.get("description", "")
    except Exception as e:
        print(f"Polygon error: {e}")

EVENT_PROMPT = (
    "You are a financial event analyzer. Classify HEADLINE + SUMMARY. "
    "Return JSON with event, assets_affected (tickers/ETFs), direction (long/short), "
    "confidence (0-100), reason, category (macro, earnings, geopolitical, etc)."
)

def process():
    for source in (fetch_rss, fetch_newsapi, fetch_finnhub, fetch_polygon):
        for title, summary in source():
            uid = sha(title)
            if headline_seen(uid):
                continue
            try:
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": EVENT_PROMPT},
                        {"role": "user", "content": f"HEADLINE: {title}\nSUMMARY: {summary}"}
                    ],
                    temperature=0.2,
                )
                data = json.loads(resp.choices[0].message.content)
                if data.get("confidence", 0) < 60:
                    continue
                DB.execute("""
                    INSERT OR REPLACE INTO events
                    (id, headline, summary, timestamp, category, direction, confidence, sentiment, reason, assets)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    uid,
                    title,
                    summary,
                    datetime.utcnow().isoformat(),
                    data.get("category", ""),
                    data.get("direction", ""),
                    data.get("confidence", 0),
                    "unknown",
                    data.get("reason", ""),
                    json.dumps(data.get("assets_affected", []))
                ))
                DB.commit()
                print(f"✅ Event saved: {title}")
            except Exception as e:
                print(f"GPT error: {e}")

if __name__ == "__main__":
    process()
