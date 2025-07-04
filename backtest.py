import pandas as pd
import yfinance as yf
import json
import matplotlib.pyplot as plt

df = pd.read_csv("headlines.csv")

initial_equity = 100_000
stop_loss_pct = -3.0
take_profit_pct = 5.0
min_volatility_pct = 0.2
max_trades_per_event = 3

equity = initial_equity
equity_curve = [equity]
trade_log = []

for _, row in df.iterrows():
    headline = row['headline']
    summary = row['summary']
    assets = json.loads(row['assets'])
    direction = row['direction']
    confidence = row['confidence']
    reason = row['reason']
    category = row['category']
    timestamp = row['timestamp']

    trades_count = 0
    for symbol in assets:
        if trades_count >= max_trades_per_event:
            break
        try:
            data = yf.Ticker(symbol).history(period="7d")
            if data.empty:
                continue
            prices = data['Close']
            entry_price = prices.iloc[0]
            vol = prices.pct_change().std() * 100
            if vol < min_volatility_pct:
                continue
            exit_price = None
            for price in prices:
                pnl = (price - entry_price) / entry_price * 100
                if direction == "short":
                    pnl = -pnl
                if pnl <= stop_loss_pct:
                    exit_price = price
                    break
                elif pnl >= take_profit_pct:
                    exit_price = price
                    break
            if exit_price is None:
                exit_price = prices.iloc[-1]
            pnl_final = (exit_price - entry_price) / entry_price * 100
            if direction == "short":
                pnl_final = -pnl_final
            equity += 1000 * pnl_final / 100
            equity_curve.append(equity)
            trade_log.append({
                "date": timestamp,
                "symbol": symbol,
                "side": direction,
                "pnl_pct": pnl_final,
                "reason": reason,
                "category": category
            })
            trades_count += 1
        except Exception as e:
            print(f"Error: {e}")

print("\nBacktest complete.")
df_trades = pd.DataFrame(trade_log)
df_trades.to_csv("backtest_results.csv", index=False)
plt.plot(equity_curve)
plt.title("Equity Curve")
plt.show()
