import pandas as pd
import numpy as np
import yfinance as yf
import json

# Load your saved event signals
df = pd.read_csv("headlines.csv")

# Define parameter ranges
conf_thresholds = [60, 70, 80]
position_sizes = [0.02, 0.05, 0.1]
stop_losses = [-2.0, -5.0, -10.0]
take_profits = [2.0, 5.0, 10.0]

results = []

for conf in conf_thresholds:
    for pos_size in position_sizes:
        for sl in stop_losses:
            for tp in take_profits:
                pnl_total = 0
                trades_taken = 0
                for _, row in df.iterrows():
                    if row["confidence"] < conf:
                        continue
                    try:
                        assets = json.loads(row["assets"])
                    except:
                        continue
                    for asset in assets:
                        try:
                            data = yf.Ticker(asset).history(period="5d")
                            entry = data["Close"].iloc[0]
                            exit_price = data["Close"].iloc[-1]
                            change_pct = (exit_price - entry) / entry * 100
                            if row["direction"] == "short":
                                change_pct = -change_pct
                            if change_pct <= sl:
                                final_exit = entry * (1 + sl/100)
                                pnl = sl
                            elif change_pct >= tp:
                                final_exit = entry * (1 + tp/100)
                                pnl = tp
                            else:
                                pnl = change_pct
                            pnl_total += pnl
                            trades_taken += 1
                        except Exception as e:
                            continue
                avg_pnl = pnl_total / trades_taken if trades_taken > 0 else 0
                results.append({
                    "conf": conf,
                    "pos_size": pos_size,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "trades": trades_taken,
                    "avg_pnl": avg_pnl
                })

# Convert to DataFrame
opt = pd.DataFrame(results)
print(opt.sort_values(by="avg_pnl", ascending=False))

# Save to CSV
opt.to_csv("parameter_optimization_results.csv", index=False)
print("✅ Optimization results saved to parameter_optimization_results.csv")
