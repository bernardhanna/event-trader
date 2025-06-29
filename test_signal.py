from event_trader import mark_event, pos_size, place_trade, tg, sha

test_evt = {
    "event": "Test Event",
    "assets_affected": ["AAPL"],
    "direction": "short",
    "confidence": 95,
    "reason": "Testing manual injection",
    "event_type": "other"
}

# Mark the event in the DB/log
mark_event(
    sha("Manual Test"),   # consistent event ID
    "Manual Test",
    "Testing summary",
    test_evt['confidence'],
    test_evt['direction'],
    test_evt['reason'],
    test_evt['event_type']
)

# Calculate size
size = pos_size(test_evt["confidence"])

# Actually place the trade
place_trade("AAPL", "short", size)

# Notify Telegram
tg(
    f"🔥 *Event Signal* ({test_evt['confidence']}%)\n"
    f"*Headline:* Manual Test\n"
    f"*Direction:* short\n"
    f"*Reason:* Testing manual injection\n"
    f"*Position size:* €{size}\n"
    f"*Asset:* `AAPL`\n"
    f"Exec: ✅"
)
