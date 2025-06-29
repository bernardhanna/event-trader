import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
from datetime import datetime
import alpaca_trade_api as trade_api
from dotenv import load_dotenv
import os

st.set_page_config(page_title="EventTrader Dashboard", layout="wide")
st.title("📊 EventTrader Dashboard")

load_dotenv()

# databases
db_conn = sqlite3.connect("events.db", check_same_thread=False)
trades_conn = sqlite3.connect("trades.db", check_same_thread=False)

# Alpaca
ALPACA_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
ALPACA_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

try:
    alpaca = trade_api.REST(ALPACA_KEY, ALPACA_SECRET, base_url=ALPACA_URL)
except Exception as e:
    st.error(f"Alpaca connection error: {e}")
    alpaca = None

# performance
trades_cursor = trades_conn.cursor()
trades_cursor.execute("""
CREATE TABLE IF NOT EXISTS performance (
    id TEXT PRIMARY KEY,
    pnl_pct REAL,
    timestamp TEXT
)
""")
trades_conn.commit()

# options trades
trades_cursor.execute("""
CREATE TABLE IF NOT EXISTS options_trades (
    id TEXT PRIMARY KEY,
    symbol TEXT,
    option_type TEXT,
    strike REAL,
    expiry TEXT,
    side TEXT,
    premium REAL,
    confidence INTEGER,
    approved INTEGER,
    timestamp TEXT
)
""")
trades_conn.commit()

# load events
events_df = pd.read_sql_query("SELECT * FROM events ORDER BY timestamp DESC LIMIT 50", db_conn)

# load trades
trades_cursor.execute("""
CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    headline TEXT,
    symbol TEXT,
    side TEXT,
    qty REAL,
    confidence INTEGER,
    approved INTEGER,
    timestamp TEXT
)
""")
trades_conn.commit()

approved_ids = [ row[0] for row in trades_cursor.execute(
    "SELECT id FROM trades WHERE approved=1").fetchall() ]

# show pending signals
pending = events_df[~events_df['id'].isin(approved_ids)]
st.subheader("⚡ Pending Signals")
if pending.empty:
    st.info("No pending signals.")
else:
    for idx, row in pending.iterrows():
        st.markdown(f"**Headline**: {row['headline']}")
        st.markdown(f"**Confidence**: {row['confidence']}%")
        st.markdown(f"**Direction**: {row['direction']}")
        st.markdown(f"**Reason**: {row['reason']}")
        st.markdown(f"**Event Type**: `{row.get('event_type', 'N/A')}`")
        if st.button(f"✅ Approve {row['headline']}", key=row['id']):
            trades_cursor.execute("""
                INSERT OR REPLACE INTO trades
                (id, headline, symbol, side, qty, confidence, approved, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['id'],
                row['headline'],
                None,
                row['direction'],
                None,
                row['confidence'],
                1,
                datetime.utcnow().isoformat()
            ))
            trades_conn.commit()
            st.success(f"Approved {row['headline']}")

# show sector counts
sector_counts = (
    events_df['event_type'].value_counts().to_dict()
    if 'event_type' in events_df.columns else {}
)
if sector_counts:
    st.write("**Approved Trades by Sector/Event Type**")
    st.json(sector_counts)

# ============================
# OPTIONS SIGNALS MODULE
# ============================

st.subheader("📝 Pending Options Signals")

options_pending = pd.read_sql_query(
    "SELECT * FROM options_trades WHERE approved=0",
    trades_conn
)

if options_pending.empty:
    st.info("No pending options signals.")
else:
    for idx, row in options_pending.iterrows():
        st.markdown(f"**Symbol**: {row['symbol']}")
        st.markdown(f"**Type**: {row['option_type']}")
        st.markdown(f"**Strike**: {row['strike']}")
        st.markdown(f"**Expiry**: {row['expiry']}")
        st.markdown(f"**Side**: {row['side']}")
        st.markdown(f"**Premium**: {row['premium']}")
        st.markdown(f"**Confidence**: {row['confidence']}%")
        if st.button(f"✅ Approve {row['symbol']} {row['strike']}{row['option_type']}", key=row['id']):
            trades_cursor.execute("""
                UPDATE options_trades SET approved=1 WHERE id=?
            """, (row['id'],))
            trades_conn.commit()
            st.success(f"Approved {row['symbol']} {row['strike']}{row['option_type']}")

# ============================
# OPTIONS SIMULATOR
# ============================

st.subheader("📈 Options Performance Simulator")

approved_options = pd.read_sql_query(
    "SELECT * FROM options_trades WHERE approved=1",
    trades_conn
)

if not approved_options.empty:
    simulated_opts = []
    for _, opt in approved_options.iterrows():
        try:
            data = yf.Ticker(opt['symbol']).history(period="30d", interval="1d")
            spot = data['Close'].iloc[-1]
            if opt['option_type'] == "C":
                intrinsic = max(spot - opt['strike'], 0)
            else:
                intrinsic = max(opt['strike'] - spot, 0)
            pnl_pct = ((intrinsic - opt['premium']) / opt['premium']) * 100
            simulated_opts.append({
                "symbol": opt['symbol'],
                "type": opt['option_type'],
                "strike": opt['strike'],
                "expiry": opt['expiry'],
                "side": opt['side'],
                "premium": opt['premium'],
                "pnl_pct": pnl_pct
            })
        except Exception as e:
            st.warning(f"Options sim error for {opt['symbol']}: {e}")
    if simulated_opts:
        st.dataframe(pd.DataFrame(simulated_opts))
    else:
        st.info("No approved options to simulate yet.")
else:
    st.info("No approved options to simulate yet.")

# ============================
# BROKER EXECUTION
# ============================

st.subheader("🔍 Broker Execution Monitor")

if alpaca:
    try:
        orders = alpaca.list_orders(status="all", limit=10)
        for order in orders:
            st.write(f"{order.symbol} | {order.side} | {order.qty} @ {order.filled_avg_price} | {order.status}")
    except Exception as e:
        st.warning(f"Could not load orders: {e}")
else:
    st.info("Alpaca not connected.")

# ============================
# Options Signals Manual Entry
# ============================

st.subheader("➕ Manually Add Option Signal")

with st.form("add_option"):
    opt_symbol = st.text_input("Underlying Symbol")
    opt_type = st.selectbox("Option Type", ["C", "P"])
    opt_strike = st.number_input("Strike Price", min_value=0.0)
    opt_expiry = st.text_input("Expiry (YYYY-MM-DD)")
    opt_side = st.selectbox("Side", ["buy", "sell"])
    opt_premium = st.number_input("Premium Paid", min_value=0.0)
    opt_conf = st.slider("Confidence", 0, 100, 50)
    submitted = st.form_submit_button("Submit Option Signal")
    if submitted:
        opt_id = f"{opt_symbol}_{opt_strike}_{opt_expiry}_{datetime.utcnow().isoformat()}"
        trades_cursor.execute("""
            INSERT INTO options_trades
            (id, symbol, option_type, strike, expiry, side, premium, confidence, approved, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """, (
            opt_id,
            opt_symbol,
            opt_type,
            opt_strike,
            opt_expiry,
            opt_side,
            opt_premium,
            opt_conf,
            datetime.utcnow().isoformat()
        ))
        trades_conn.commit()
        st.success("Option signal added!")

