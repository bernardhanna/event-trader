# Event Trader

Event Trader ingests news headlines and tweets, classifies them with AI models
and optionally places trades through the Alpaca API. A Streamlit dashboard lets
you approve signals and review performance.

## Prerequisites

- Python **3.11** or later
- API keys for OpenAI, Gemini, Telegram and Alpaca

## Setup

1. Create a `.env` file in the project root with the following variables:

   ```env
   OPENAI_API_KEY=your-openai-key
   GEMINI_API_KEY=your-google-gemini-key
   TELEGRAM_BOT_TOKEN=your-telegram-bot-token
   TELEGRAM_CHAT_ID=your-chat-id
   ALPACA_API_KEY=your-alpaca-key
   ALPACA_SECRET_KEY=your-alpaca-secret
   # optional: custom Alpaca base URL
   ALPACA_BASE_URL=https://paper-api.alpaca.markets
   ```

2. Install dependencies and activate the virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Run the trader bot or dashboard:

   ```bash
   python event_trader.py        # command line bot
   streamlit run streamlit_app.py
   ```

## Optional scripts

- `backtest.py` – simulate historical performance using the saved
  `headlines.csv` file and produce an equity curve.
- `parameter_optimizer.py` – grid search over different confidence thresholds
  and position sizing to produce `parameter_optimization_results.csv`.

## Configuration

`feeds.json` holds the RSS feeds used for news scanning. Customize the list as
needed. `whitelisted_accounts.json` contains Twitter accounts that are deemed
trustworthy. Set `NEWS_MAX_AGE_HOURS` to control how far back the bot will look
for headlines. It defaults to **12** hours.

Set `NEWS_MAX_AGE_HOURS` to control how far back the bot will look when
scanning RSS feeds. It defaults to **12** hours. Increase this if the script
is not run often and you want older headlines to be considered.

When a processing cycle finds no trading opportunities, the bot sends a
"heartbeat" notification to Telegram (or logs to stdout) so you know it is
still running.