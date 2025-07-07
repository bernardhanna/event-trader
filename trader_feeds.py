import feedparser

TRADER_FEEDS = [
    "https://traderfeed.blogspot.com/feeds/posts/default",           # TraderFeed (Brett Steenbarger)
    "https://themacrotourist.substack.com/feed",                     # MacroTourist
    "https://alphaideas.in/feed/",                                    # Alpha Ideas
    "https://hhhypergrowth.substack.com/feed",                       # hhhypergrowth
    "https://kailashconcepts.substack.com/feed",                      # Kailash Concepts
    "https://sentimentrader.substack.com/feed",                      # Sentimentrader
    "https://themarketear.substack.com/feed",                         # MarketEar
    "https://ftalphaville.ft.com/feed/",                               # FT Alphaville
    "https://macrovoices.com/feed?format=feed&type=rss",              # MacroVoices
    "https://www.valuewalk.com/feed/",                                 # ValueWalk
    "https://seekingalpha.com/market_currents.xml",                   # Seeking Alpha
    "https://www.oftwominds.com/blog.xml",                             # Charles Hugh Smith
    "https://finviz.com/feed.ashx",                                    # Finviz News
    "https://www.hedgeye.com/rss",                                     # Hedgeye
    "https://www.realvision.com/rss",                                  # Real Vision
    "https://newsletter.rampcapitalllc.com/feed",                      # Ramp Capital
    "https://thetranscript.substack.com/feed",                         # The Transcript
    "https://feeds.marketwatch.com/marketwatch/topstories/",           # Marketwatch Top
    "https://www.zerohedge.com/fullrss2.xml",                          # Zerohedge
    "https://www.bloomberg.com/feed/podcast/etf-report.xml"            # Bloomberg ETF Report
]

def fetch_trader_news():
    stories = []
    for url in TRADER_FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                stories.append({
                    "title": e.title,
                    "summary": getattr(e, "summary", ""),
                    "link": e.link,
                    "published": getattr(e, "published", "")
                })
        except Exception as ex:
            print(f"[TraderFeed error] {url} {ex}")
    return stories
