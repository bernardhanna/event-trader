# event-trader

### Configuration

Set `NEWS_MAX_AGE_HOURS` to control how far back the bot will look when
scanning RSS feeds. It defaults to **12** hours. Increase this if the script
is not run often and you want older headlines to be considered.

### Twitter Access

To pull tweets from the accounts listed in `whitelisted_accounts.json`, create a
Twitter/X developer application and generate a **Bearer Token**. Export this as
`TWITTER_BEARER_TOKEN` in your environment before running the bot.
