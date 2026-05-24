"""
app.py — Streamlit Dashboard
AI-Powered Stock Market Monitor
Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import threading
import time
import yfinance as yf
from datetime import datetime, timedelta

from database import (
    get_watchlist, add_stock, remove_stock,
    get_recent_alerts, get_price_cache,
)
from analyzer  import analyze_stock, fetch_data
from alerts    import dispatch_alert

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Stock Monitor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .metric-card {
        background: linear-gradient(135deg, #1e2130 0%, #252840 100%);
        border-radius: 12px;
        padding: 18px;
        border-left: 4px solid;
        margin-bottom: 10px;
    }
    .buy-card  { border-color: #00d084; }
    .sell-card { border-color: #ff4b4b; }
    .hold-card { border-color: #ffa500; }
    .signal-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.9em;
    }
    .badge-buy       { background: #00d08430; color: #00d084; }
    .badge-sell      { background: #ff4b4b30; color: #ff4b4b; }
    .badge-hold      { background: #ffa50030; color: #ffa500; }
    .badge-strongbuy { background: #00ff8860; color: #00ff88; }
    .sidebar-title { font-size: 1.3em; font-weight: bold; color: #00d084; }
</style>
""", unsafe_allow_html=True)


# ── Background monitor thread ──────────────────────────────────────────────────

def start_background_monitor():
    """Launch monitor.py in a background thread (only once)."""
    if "monitor_started" not in st.session_state:
        from monitor import run_cycle
        def _loop():
            while True:
                try:
                    run_cycle()
                except Exception:
                    pass
                time.sleep(5 * 60)   # 5-minute cycle

        t = threading.Thread(target=_loop, daemon=True)
        t.start()
        st.session_state["monitor_started"] = True


# ── Sidebar navigation ────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown('<p class="sidebar-title">📈 AI Stock Monitor</p>', unsafe_allow_html=True)
    st.caption("Powered by yfinance + TA")
    st.divider()
    
    page = st.radio(
        "Navigation",
        ["🏠 Dashboard", "➕ Add Stock", "📊 Deep Analysis", "🔔 Alert History", "📋 Market Close", "⚙️ Settings"],
        label_visibility="collapsed",
    )
    
    st.divider()
    st.caption("Auto-refresh every 5 min")
    if st.button("🔄 Refresh Now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

if page == "🏠 Dashboard":
    st.title("📈 AI Stock Market Monitor")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    watchlist = get_watchlist()
    cache     = get_price_cache()

    if not watchlist:
        st.info("👋 Your watchlist is empty. Go to **➕ Add Stock** to get started.")
        st.stop()

    # ── Summary metrics ────────────────────────────────────────────────────
    total_stocks = len(watchlist)
    buy_signals  = sum(1 for t in watchlist
                      if "BUY" in cache.get(t["ticker"], {}).get("recommendation", ""))
    sell_signals = sum(1 for t in watchlist
                      if "SELL" in cache.get(t["ticker"], {}).get("recommendation", ""))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📋 Watching", total_stocks)
    col2.metric("✅ Buy Signals",  buy_signals)
    col3.metric("🔴 Sell Signals", sell_signals)
    col4.metric("⏸️ Hold", total_stocks - buy_signals - sell_signals)

    st.divider()

    # ── Per-stock cards ────────────────────────────────────────────────────
    for stock in watchlist:
        ticker = stock["ticker"]
        cached = cache.get(ticker, {})
        
        # Use cached data if available, else show loading state
        price     = cached.get("price", "—")
        change    = cached.get("change_pct", 0)
        rsi       = cached.get("rsi", "—")
        rec       = cached.get("recommendation", "Loading…")
        ema20     = cached.get("ema20", "—")
        ema50     = cached.get("ema50", "—")

        color = "#00d084" if price != "—" and float(price) <= stock["buy_price"] * 1.02 else (
                "#ff4b4b" if price != "—" and float(price) >= stock["sell_price"] * 0.98 else "#ffa500")

        with st.expander(
            f"**{stock['company']} ({ticker})**  —  "
            f"{'$' if stock['currency'] == 'USD' else ''}{price}  "
            f"({'📈' if change >= 0 else '📉'} {change:+.2f}%)",
            expanded=True
        ):
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("💰 Price",      f"{price}")
            c2.metric("🎯 Buy Target", f"{stock['buy_price']}")
            c3.metric("📤 Sell Target",f"{stock['sell_price']}")
            c4.metric("⛔ Stop Loss",  f"{stock['stop_loss']}")
            c5.metric("🤖 Signal",     rec)

            c6, c7, c8, c9 = st.columns(4)
            c6.metric("RSI",  rsi)
            c7.metric("EMA20", ema20)
            c8.metric("EMA50", ema50)
            if price != "—":
                pnl = round((float(price) - stock["buy_price"]) * stock["quantity"], 2)
                pnl_str = f"+${pnl}" if pnl >= 0 else f"-${abs(pnl)}"
                c9.metric("Est. P&L", pnl_str, delta=pnl_str)

            # Quick action buttons
            b1, b2, _ = st.columns([1, 1, 4])
            if b1.button(f"📊 Analyze", key=f"analyze_{ticker}"):
                st.session_state["analyze_ticker"] = ticker
                st.rerun()
            if b2.button(f"🗑️ Remove", key=f"remove_{ticker}"):
                remove_stock(ticker)
                st.success(f"Removed {ticker} from watchlist.")
                time.sleep(1)
                st.rerun()

    # Start background monitor after rendering
    start_background_monitor()


# ── ADD STOCK ─────────────────────────────────────────────────────────────────

elif page == "➕ Add Stock":
    st.title("➕ Add Stock to Watchlist")
    st.caption("Enter your stock details below. The AI will start monitoring immediately.")

    with st.form("add_stock_form"):
        c1, c2 = st.columns(2)
        company   = c1.text_input("Company Name",    placeholder="e.g. Apple Inc.")
        ticker    = c2.text_input("Ticker Symbol",   placeholder="e.g. AAPL")
        
        c3, c4 = st.columns(2)
        exchange  = c3.selectbox("Exchange", ["NASDAQ", "NYSE", "NSE", "BSE", "LSE", "OTHER"])
        currency  = c4.selectbox("Currency", ["USD", "INR", "NPR", "GBP", "EUR"])

        st.subheader("🎯 Price Targets")
        c5, c6, c7, c8 = st.columns(4)
        buy_price  = c5.number_input("Buy Price",   min_value=0.01, value=100.0, step=0.5)
        sell_price = c6.number_input("Sell Price",  min_value=0.01, value=120.0, step=0.5)
        stop_loss  = c7.number_input("Stop Loss",   min_value=0.01, value=90.0,  step=0.5)
        quantity   = c8.number_input("Quantity",    min_value=0.01, value=10.0,  step=1.0)

        submitted = st.form_submit_button("✅ Add to Watchlist", use_container_width=True)

        if submitted:
            if not company or not ticker:
                st.error("Company name and ticker are required.")
            elif buy_price >= sell_price:
                st.error("Sell price must be higher than buy price.")
            elif stop_loss >= buy_price:
                st.error("Stop loss must be below buy price.")
            else:
                success = add_stock(
                    company=company,
                    ticker=ticker.upper(),
                    buy_price=buy_price,
                    sell_price=sell_price,
                    stop_loss=stop_loss,
                    quantity=quantity,
                    exchange=exchange,
                    currency=currency,
                )
                if success:
                    st.success(f"✅ {company} ({ticker.upper()}) added to watchlist!")
                    st.balloons()
                else:
                    st.error("Failed to add stock.")


# ── DEEP ANALYSIS ─────────────────────────────────────────────────────────────

elif page == "📊 Deep Analysis":
    st.title("📊 Deep Technical Analysis")

    watchlist = get_watchlist()
    if not watchlist:
        st.info("Add stocks first.")
        st.stop()

    # Pre-select if triggered from dashboard
    default_ticker = st.session_state.get("analyze_ticker", watchlist[0]["ticker"])
    tickers        = [s["ticker"] for s in watchlist]
    default_idx    = tickers.index(default_ticker) if default_ticker in tickers else 0

    selected_ticker = st.selectbox("Select Stock", tickers, index=default_idx)
    stock_info      = next((s for s in watchlist if s["ticker"] == selected_ticker), None)

    if not stock_info:
        st.stop()

    with st.spinner(f"Analyzing {selected_ticker}…"):
        result = analyze_stock(stock_info)

    if result is None:
        st.error("Could not fetch data. Check ticker or internet connection.")
        st.stop()

    # ── Signal banner ──────────────────────────────────────────────────────
    signal = result["signal"]
    if "STRONG BUY" in signal:
        st.success(f"## 🤖 AI Decision: {signal}")
    elif "BUY" in signal:
        st.success(f"## 🤖 AI Decision: {signal}")
    elif "STRONG SELL" in signal:
        st.error(f"## 🤖 AI Decision: {signal}")
    elif "SELL" in signal:
        st.error(f"## 🤖 AI Decision: {signal}")
    else:
        st.warning(f"## 🤖 AI Decision: {signal}")

    # ── Key metrics ────────────────────────────────────────────────────────
    st.subheader("Key Metrics")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Price",     f"{result['price']}", f"{result['change_pct']:+.2f}%")
    m2.metric("RSI",       f"{result['rsi']}", "Oversold" if result['rsi'] < 30 else ("Overbought" if result['rsi'] > 70 else "Normal"))
    m3.metric("MACD",      f"{result['macd']}")
    m4.metric("EMA 20",    f"{result['ema20']}")
    m5.metric("EMA 50",    f"{result['ema50']}")
    m6.metric("Score",     f"{result['score']:+d} / 10")

    st.divider()

    # ── Two columns: indicators + chart ───────────────────────────────────
    left, right = st.columns([1, 2])

    with left:
        st.subheader("📋 Indicator Summary")
        ind_data = {
            "Indicator": ["RSI (14)", "MACD", "Signal Line", "EMA 20", "EMA 50",
                          "Support", "Resistance", "Breakout", "Candle Pattern",
                          "Volume vs Avg"],
            "Value": [
                result["rsi"],
                result["macd"],
                result["signal_line"],
                result["ema20"],
                result["ema50"],
                result["support"],
                result["resistance"],
                result["breakout"],
                result["candle"],
                f"{result['volume_info']['pct_change']:+.1f}%",
            ]
        }
        st.dataframe(pd.DataFrame(ind_data), hide_index=True, use_container_width=True)

        st.subheader("💡 AI Reasoning")
        for reason in result["reasons"]:
            st.markdown(f"- {reason}")

    with right:
        st.subheader("📈 Price Chart (3 months)")
        df = fetch_data(selected_ticker, period="3mo", interval="1d")
        if df is not None:
            fig = go.Figure()

            # Candlestick
            fig.add_trace(go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"],
                low=df["Low"],  close=df["Close"],
                name="Price", increasing_line_color="#00d084",
                decreasing_line_color="#ff4b4b",
            ))

            # EMA lines
            ema20_series = df["Close"].ewm(span=20, adjust=False).mean()
            ema50_series = df["Close"].ewm(span=50, adjust=False).mean()
            fig.add_trace(go.Scatter(x=df.index, y=ema20_series,
                name="EMA 20", line=dict(color="#ffa500", width=1.5)))
            fig.add_trace(go.Scatter(x=df.index, y=ema50_series,
                name="EMA 50", line=dict(color="#4fc3f7", width=1.5)))

            # Buy/Sell/Stop lines
            fig.add_hline(y=result["buy_price"],  line_color="#00d084",
                          line_dash="dash", annotation_text="BUY")
            fig.add_hline(y=result["sell_price"], line_color="#ff4b4b",
                          line_dash="dash", annotation_text="SELL")
            fig.add_hline(y=result["stop_loss"],  line_color="#ff6600",
                          line_dash="dot",  annotation_text="STOP")

            fig.update_layout(
                template="plotly_dark",
                height=400,
                margin=dict(l=0, r=0, t=30, b=0),
                xaxis_rangeslider_visible=False,
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── P&L section ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("💰 P&L Estimate")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Buy at",           f"${result['buy_price']} x{result['qty']}")
    p2.metric("Target Profit",    f"${result['potential_profit']:+.2f}")
    p3.metric("Unrealised P&L",   f"${result['unrealized_pnl']:+.2f}",
              delta=f"${result['unrealized_pnl']:+.2f}")
    p4.metric("Stop-loss Risk",   f"${round((result['buy_price'] - result['stop_loss']) * result['qty'], 2):.2f}")

    # ── Manual alert button ────────────────────────────────────────────────
    st.divider()
    if st.button("📲 Send WhatsApp Alert Now", use_container_width=True):
        sent = dispatch_alert(result, force=True)
        if sent:
            st.success("✅ WhatsApp alert sent!")
        else:
            st.warning("Alert printed to console (configure Twilio for WhatsApp).")


# ── ALERT HISTORY ─────────────────────────────────────────────────────────────

elif page == "🔔 Alert History":
    st.title("🔔 Alert History")

    alerts = get_recent_alerts(limit=100)

    if not alerts:
        st.info("No alerts fired yet. The system will alert you when conditions are met.")
        st.stop()

    df = pd.DataFrame(alerts)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df = df.sort_values("created_at", ascending=False)

    # Summary
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Alerts", len(df))
    c2.metric("Sent via WhatsApp", df["sent"].sum())
    c3.metric("Unique Stocks", df["ticker"].nunique())

    st.divider()

    # Color coding
    def colour_signal(val):
        if "BUY" in str(val):   return "background-color: #00d08420; color: #00d084"
        if "SELL" in str(val):  return "background-color: #ff4b4b20; color: #ff4b4b"
        return ""

    display_cols = ["created_at", "ticker", "alert_type", "signal", "price", "sent"]
    styled = df[display_cols].style.applymap(colour_signal, subset=["signal"])
    st.dataframe(styled, hide_index=True, use_container_width=True)


# ── MARKET CLOSE SUMMARY ──────────────────────────────────────────────────────

elif page == "📋 Market Close":
    st.title("📋 Market Close Summary")
    st.caption("Closing prices and AI signals for all your NEPSE stocks")

    import pytz
    npt        = pytz.timezone("Asia/Kathmandu")
    now_npt    = datetime.now(npt)
    market_closed = now_npt.hour >= 15 or now_npt.hour < 11

    if market_closed:
        st.success("🔴 NEPSE Market is CLOSED — Showing last closing prices")
    else:
        st.warning("🟢 NEPSE Market is OPEN (11 AM – 3 PM) — Prices updating live")

    watchlist = get_watchlist()
    if not watchlist:
        st.info("Add stocks first from ➕ Add Stock")
        st.stop()

    # ── Fetch closing prices for all stocks ───────────────────────────────
    st.subheader("📊 Today's Closing Summary")

    rows = []
    progress = st.progress(0, text="Fetching closing prices...")

    for i, stock in enumerate(watchlist):
        ticker = stock["ticker"]
        progress.progress((i + 1) / len(watchlist), text=f"Fetching {ticker}...")

        try:
            result = analyze_stock(stock)
            if result:
                price     = result["price"]
                change    = result["change_pct"]
                signal    = result["signal"]
                rsi       = result["rsi"]
                buy_p     = stock["buy_price"]
                sell_p    = stock["sell_price"]
                stop_p    = stock["stop_loss"]

                # Decision
                if price <= buy_p * 1.01:
                    action = "🟢 BUY"
                elif price >= sell_p * 0.99:
                    action = "🔴 SELL"
                elif price <= stop_p * 1.02:
                    action = "⛔ STOP LOSS"
                else:
                    action = "⏸️ HOLD"

                rows.append({
                    "Company":      stock["company"],
                    "Ticker":       ticker,
                    "Close Price":  f"NPR {price:,.2f}",
                    "Change":       f"{change:+.2f}%",
                    "RSI":          rsi,
                    "AI Signal":    signal,
                    "Action":       action,
                    "Buy Target":   f"NPR {buy_p:,.2f}",
                    "Sell Target":  f"NPR {sell_p:,.2f}",
                })
        except Exception as e:
            rows.append({
                "Company": stock["company"],
                "Ticker":  ticker,
                "Close Price": "—",
                "Change": "—",
                "RSI": "—",
                "AI Signal": "Error",
                "Action": "—",
                "Buy Target": f"NPR {stock['buy_price']:,.2f}",
                "Sell Target": f"NPR {stock['sell_price']:,.2f}",
            })

    progress.empty()

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, use_container_width=True)

        # ── Summary counts ─────────────────────────────────────────────
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Stocks",  len(rows))
        c2.metric("🟢 BUY",   sum(1 for r in rows if "BUY"  in r["Action"]))
        c3.metric("🔴 SELL",  sum(1 for r in rows if "SELL" in r["Action"]))
        c4.metric("⏸️ HOLD",  sum(1 for r in rows if "HOLD" in r["Action"]))

        # ── Send WhatsApp summary ──────────────────────────────────────
        st.divider()
        st.subheader("📲 Send Close Summary to WhatsApp")

        if st.button("📲 Send Market Close Summary to WhatsApp", use_container_width=True):
            from alerts import send_whatsapp
            lines = [f"📊 *NEPSE Market Close Summary*",
                     f"🕒 {now_npt.strftime('%Y-%m-%d %H:%M')} NPT\n"]
            for r in rows:
                lines.append(
                    f"{r['Ticker']}: {r['Close Price']} ({r['Change']}) — {r['Action']}"
                )
            lines.append("\n_AI Stock Monitor_")
            msg  = "\n".join(lines)
            sent = send_whatsapp(msg)
            if sent:
                st.success("✅ Summary sent to WhatsApp!")
            else:
                st.warning("Twilio not configured. Summary printed below:")
                st.code(msg)

        # ── Auto-schedule note ─────────────────────────────────────────
        st.info(
            "💡 **Tip:** To receive this summary automatically at 3:15 PM every day, "
            "complete the Twilio setup in ⚙️ Settings."
        )


# ── SETTINGS ──────────────────────────────────────────────────────────────────

elif page == "⚙️ Settings":
    st.title("⚙️ Settings & Setup")

    tab1, tab2, tab3 = st.tabs(["📱 WhatsApp Setup", "🔑 API Keys", "ℹ️ System Info"])

    with tab1:
        st.subheader("Twilio WhatsApp (Free Sandbox) Setup")
        st.markdown("""
**Step 1: Create a free Twilio account**
1. Go to [twilio.com](https://www.twilio.com) → Sign up (free)
2. Go to **Messaging > Try it out > Send a WhatsApp message**
3. Note your **Account SID** and **Auth Token**

**Step 2: Activate the WhatsApp Sandbox**
1. Send `join <your-sandbox-word>` to **+1 415 523 8886** on WhatsApp
2. You will receive a confirmation

**Step 3: Set environment variables in your `.env` file**
```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:+977XXXXXXXXXX
```

**Step 4: Restart the app** — alerts will now go to your WhatsApp!
        """)

        st.subheader("Test WhatsApp Connection")
        if st.button("📲 Send Test Message"):
            from alerts import send_whatsapp
            ok = send_whatsapp("✅ Test message from AI Stock Monitor! Your alerts are working.")
            if ok:
                st.success("Test message sent! Check your WhatsApp.")
            else:
                st.warning("Twilio not configured. Check your .env file.")

    with tab2:
        st.subheader("Free API Keys")
        st.markdown("""
| Service | Free Tier | Link |
|---------|-----------|------|
| **Yahoo Finance (yfinance)** | ✅ Unlimited | No key needed |
| **Alpha Vantage** | 25 req/day | [alphavantage.co](https://www.alphavantage.co/support/#api-key) |
| **Finnhub** | 60 req/min | [finnhub.io](https://finnhub.io/register) |
| **Twelve Data** | 800 req/day | [twelvedata.com](https://twelvedata.com/register) |
| **Twilio Sandbox** | Free | [twilio.com](https://twilio.com) |

> **Tip:** yfinance covers 95% of needs. Only add other APIs if yfinance fails for a specific ticker.
        """)

    with tab3:
        st.subheader("System Information")
        import sys
        st.json({
            "python_version": sys.version,
            "monitor_interval": f"{os.getenv('MONITOR_INTERVAL_MINUTES', 5)} minutes",
            "alert_cooldown":   f"{os.getenv('ALERT_COOLDOWN_MINUTES', 30)} minutes",
            "timezone":         os.getenv("TIMEZONE", "Asia/Kathmandu"),
            "database_path":    str(DB_PATH if 'DB_PATH' in dir() else "data/stocks.db"),
        })

import os
try:
    from database import DB_PATH
except:
    pass
