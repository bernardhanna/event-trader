import pandas as pd
import yfinance as yf
import json
import matplotlib.pyplot as plt

# Load your historical events (mock or real) CSV
df = pd.read_csv("headlines.csv")

# Backtest settings
initial_equity = 100_000
stop_loss_pct = -3.0
take_profit_pct = 5.0
min_volatility_pct = 0.2
max_trades_per_event = 3

# Portfolio simulation
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

    print(f"\nEvaluating: {headline}")

    trades_count = 0
    for symbol in assets:
        if trades_count >= max_trades_per_event:
            print("Reached max trades per event, skipping the rest.")
            break

        try:
            data = yf.Ticker(symbol).history(period="7d")
            if data.empty:
                print(f"No price data for {symbol}")
                continue

            prices = data['Close']
            entry_price = prices.iloc[0]

            # Calculate historical volatility
            vol = prices.pct_change().std() * 100
            if vol < min_volatility_pct:
                print(f"Skipping {symbol} due to low volatility ({vol:.2f}%).")
                continue

            exit_price = None
            exit_reason = None

            for price in prices:
                pnl = (price - entry_price) / entry_price * 100
                if direction == "short":
                    pnl = -pnl

                if pnl <= stop_loss_pct:
                    exit_price = price
                    exit_reason = "stop-loss"
                    break
                elif pnl >= take_profit_pct:
                    exit_price = price
                    exit_reason = "take-profit"
                    break

            if exit_price is None:
                exit_price = prices.iloc[-1]
                exit_reason = "close"

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
                "category": category,
                "exit_reason": exit_reason
            })

            trades_count += 1
            print(f"{symbol} ({direction}): entry={entry_price:.2f}, exit={exit_price:.2f}, PnL={pnl_final:.2f}%")

        except Exception as e:
            print(f"Error evaluating {symbol}: {e}")

# Backtest summary
df_trades = pd.DataFrame(trade_log)
win_rate = len(df_trades[df_trades['pnl_pct'] > 0]) / len(df_trades) * 100 if len(df_trades) else 0
avg_pnl = df_trades['pnl_pct'].mean() if len(df_trades) else 0

print("\n📊 Backtest Summary:")
print(f"Total trades: {len(df_trades)}")
print(f"Win rate: {win_rate:.2f}%")
print(f"Average PnL: {avg_pnl:.2f}%")
if len(df_trades):
    print(f"Best trade: {df_trades['pnl_pct'].max():.2f}%")
    print(f"Worst trade: {df_trades['pnl_pct'].min():.2f}%")

print("\n🔍 Trade log:")
for trade in trade_log:
    print(f"{trade['date']} | {trade['symbol']} | {trade['side']} | {trade['pnl_pct']:.2f}% | "
          f"{trade['category']} | {trade['reason']}")

# Save results
df_trades.to_csv("backtest_results.csv", index=False)

# Plot equity curve
plt.plot(equity_curve)
plt.title("Equity Curve")
plt.xlabel("Trades")
plt.ylabel("Equity (€)")
plt.grid()
plt.show()
