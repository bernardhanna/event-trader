from event_trader import mark_event, pos_size, place_trade, tg, sha

# define a test headline and summary
headline = "Test Signal: Apple announces $10B share buyback"
summary = "Apple will buy back $10 billion of its stock this quarter, citing strong cash reserves and positive future outlook."

# make a fake event ID
uid = sha(headline)

# store the event
mark_event(
    uid,
    headline,
    summary,
    90,              # confidence
    "long",          # direction
    "Strong buyback supports share price",  # reason
    "m&a",           # event_type
    "positive"       # sentiment
)

# size calculation
size = pos_size(90)

# simulate placing the trade
success, oid = place_trade("AAPL", "long", size)

# log to telegram
tg(
    f"✅ Test Signal:\n"
    f"Headline: {headline}\n"
    f"Direction: long\n"
    f"Size: €{size}\n"
    f"Exec: {'✅' if success else '❌'}"
)
