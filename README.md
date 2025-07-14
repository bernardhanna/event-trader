# event-trader

### Configuration

Set `NEWS_MAX_AGE_HOURS` to control how far back the bot will look when
scanning RSS feeds. It defaults to **12** hours. Increase this if the script
is not run often and you want older headlines to be considered.

Copy `.env.example` to `.env` and provide your API credentials. The example
file lists all environment variables used by the scripts, including
`OPENAI_API_KEY`, `GEMINI_API_KEY`, `ALPACA_API_KEY`, and others.
`ALPACA_BASE_URL` defaults to `https://paper-api.alpaca.markets` if not set.
