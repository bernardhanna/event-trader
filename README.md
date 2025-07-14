# event-trader

### Configuration

Set `NEWS_MAX_AGE_HOURS` to control how far back the bot will look when
scanning RSS feeds. It defaults to **12** hours. Increase this if the script
is not run often and you want older headlines to be considered.

When a processing cycle finds no trading opportunities, the bot sends a
"heartbeat" notification to Telegram (or logs to stdout) so you know it is
still running.
