# 📈 AI Stock Market Monitor

> A fully automated AI trading assistant that monitors stocks in real time,
> performs technical analysis, and sends **instant WhatsApp alerts**.

---

## 🚀 Quick Start (5 minutes)

### 1. Clone or download this project
```bash
git clone <your-repo>
cd stock_monitor
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Open .env and fill in your Twilio credentials
```

### 4. Run the dashboard
```bash
streamlit run app.py
```

Open your browser at: **http://localhost:8501**

---

## 📱 WhatsApp Setup (Free — 5 minutes)

1. Go to [twilio.com](https://www.twilio.com) → Create free account
2. Go to **Messaging → Try it out → Send a WhatsApp message**
3. **Send this message from your WhatsApp** to `+1 415 523 8886`:
   ```
   join <your-sandbox-code>
   ```
4. Copy your **Account SID** and **Auth Token** into `.env`
5. Set `TWILIO_WHATSAPP_TO=whatsapp:+YOUR_NUMBER`

That's it — alerts will now go directly to your WhatsApp!

---

## 🔧 Running the Background Monitor

The Streamlit app starts the monitor automatically.
To run it standalone (e.g. on a server):

```bash
python monitor.py
```

This runs every 5 minutes (configurable via `MONITOR_INTERVAL_MINUTES` in `.env`).

---

## 📂 Project Structure

```
stock_monitor/
├── app.py            ← Streamlit dashboard (main UI)
├── analyzer.py       ← Technical analysis engine (RSI, MACD, EMA, etc.)
├── alerts.py         ← WhatsApp alert system (Twilio)
├── monitor.py        ← Background monitoring loop
├── database.py       ← SQLite database (watchlist, alerts, cache)
├── requirements.txt  ← Python dependencies
├── .env.example      ← Environment variables template
├── README.md         ← This file
├── data/             ← SQLite database file (auto-created)
└── logs/             ← Monitor logs (auto-created)
```

---

## 🧠 AI Signal Logic

The AI engine scores each stock from **-10 to +10** using:

| Indicator | Weight |
|-----------|--------|
| RSI (oversold/overbought) | ±2 |
| MACD crossover | ±1 |
| MACD trend | ±1 |
| EMA 20/50 alignment | ±2 |
| Breakout detection | ±2 |
| Candlestick pattern | ±1 |
| Volume confirmation | ±1 |
| Price vs targets | ±1 |

**Score interpretation:**

| Score | Signal |
|-------|--------|
| ≥ 5   | ✅ STRONG BUY |
| 2–4   | 📈 BUY |
| -1–1  | ⏸️ HOLD |
| -4–-2 | 📉 SELL |
| ≤ -5  | 🔴 STRONG SELL |

---

## 🌐 Free Deployment

### Option 1: Streamlit Cloud (Easiest)
1. Push code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect repo → Deploy
4. Add secrets in the Streamlit Cloud dashboard

### Option 2: Render (Free tier)
1. Push to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Build command: `pip install -r requirements.txt`
4. Start command: `streamlit run app.py --server.port $PORT`

### Option 3: Railway
1. Push to GitHub
2. Go to [railway.app](https://railway.app) → Deploy from GitHub
3. Set environment variables in the dashboard

---

## 📊 Example WhatsApp Alerts

**BUY Alert:**
```
🟢 BUY ALERT — Apple (AAPL)
💰 Current Price : USD 184.50
🎯 Your Buy Target: USD 185.00
📊 RSI: 28.3 (Oversold ✅)
📈 MACD: -0.42 | Signal: -0.65
📦 Volume: +22.4% vs avg
🤖 AI Signal: STRONG BUY ✅
```

**SELL Alert:**
```
🔴 SELL ALERT — Tesla (TSLA)
💰 Current Price: USD 319.80
🎯 Your Sell Target: USD 320.00
📊 RSI: 72.1 (Overbought ⚠️)
🟢 Est. P&L (x10): USD +740.00
🤖 AI Signal: SELL 📉
```

---

## ⚙️ Configuration (.env)

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:+977XXXXXXXXXX
MONITOR_INTERVAL_MINUTES=5
ALERT_COOLDOWN_MINUTES=30
TIMEZONE=Asia/Kathmandu
```

---

## ❓ FAQ

**Q: Do I need to pay for anything?**
A: No. yfinance is free, Twilio Sandbox is free, Streamlit Cloud is free.

**Q: Does it work for Indian/Nepali stocks?**
A: Yes! Use NSE tickers like `RELIANCE.NS`, `TCS.NS`. For Nepal, use `NABIL.NP` etc.

**Q: Will it run 24/7?**
A: When deployed on Render/Railway, yes. On your laptop, keep it open.

**Q: How do I add more stocks?**
A: Use the "➕ Add Stock" page in the dashboard.

---

## ⚠️ Disclaimer

This tool is for **educational and informational purposes only**.
Always do your own research. Past signals do not guarantee future performance.

---

*Built with ❤️ using Python, yfinance, Streamlit, and Twilio*
