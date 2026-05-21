"""
alerts.py — WhatsApp notification system
Uses Twilio Sandbox (free) to send instant WhatsApp messages.
Also supports email and console fallback.
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ── Twilio config ─────────────────────────────────────────────────────────────
ACCOUNT_SID   = os.getenv("TWILIO_ACCOUNT_SID", "")
AUTH_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN",   "")
FROM_NUMBER   = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
TO_NUMBER     = os.getenv("TWILIO_WHATSAPP_TO",   "")
COOLDOWN_MIN  = int(os.getenv("ALERT_COOLDOWN_MINUTES", "30"))

# Track sent alerts in-memory to avoid spam (ticker → {type → last_sent})
_sent_cache: dict[str, dict] = {}


def _within_cooldown(ticker: str, alert_type: str) -> bool:
    """Return True if an alert of this type was sent within cooldown period."""
    cache = _sent_cache.get(ticker, {})
    last  = cache.get(alert_type)
    if last and (datetime.now() - last) < timedelta(minutes=COOLDOWN_MIN):
        return True
    return False


def _mark_sent(ticker: str, alert_type: str):
    if ticker not in _sent_cache:
        _sent_cache[ticker] = {}
    _sent_cache[ticker][alert_type] = datetime.now()


# ── Message builders ──────────────────────────────────────────────────────────

def build_buy_message(data: dict) -> str:
    cur = data.get("currency", "USD")
    return f"""
🟢 *BUY ALERT — {data['company']} ({data['ticker']})*

💰 Current Price : {cur} {data['price']}
🎯 Your Buy Target: {cur} {data['buy_price']}
📊 RSI           : {data['rsi']} {'(Oversold ✅)' if data['rsi'] < 35 else ''}
📈 MACD          : {data['macd']} | Signal: {data['signal_line']}
📉 EMA 20/50     : {data['ema20']} / {data['ema50']}
📦 Volume        : {data['volume_info']['pct_change']:+.1f}% vs avg

🤖 AI Signal     : *{data['signal']}*
💡 Top Reason    : {data['reasons'][0] if data['reasons'] else '—'}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (NPT)
""".strip()


def build_sell_message(data: dict) -> str:
    cur = data.get("currency", "USD")
    pnl_sign = "🟢" if data['unrealized_pnl'] >= 0 else "🔴"
    return f"""
🔴 *SELL ALERT — {data['company']} ({data['ticker']})*

💰 Current Price  : {cur} {data['price']}
🎯 Your Sell Target: {cur} {data['sell_price']}
📊 RSI            : {data['rsi']} {'(Overbought ⚠️)' if data['rsi'] > 65 else ''}
📈 MACD           : {data['macd']} | Signal: {data['signal_line']}
📦 Volume         : {data['volume_info']['pct_change']:+.1f}% vs avg

{pnl_sign} Est. P&L (x{data['qty']}): {cur} {data['unrealized_pnl']:+.2f}
🤖 AI Signal      : *{data['signal']}*
💡 Top Reason     : {data['reasons'][0] if data['reasons'] else '—'}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (NPT)
""".strip()


def build_stoploss_message(data: dict) -> str:
    cur = data.get("currency", "USD")
    return f"""
⛔ *STOP-LOSS ALERT — {data['company']} ({data['ticker']})*

💰 Current Price  : {cur} {data['price']}
⛔ Stop-Loss Level : {cur} {data['stop_loss']}
🔻 Loss (x{data['qty']})  : {cur} {data['unrealized_pnl']:+.2f}

🤖 AI Signal      : *{data['signal']}*
⚠️  ACTION NEEDED: Consider cutting losses NOW.

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (NPT)
""".strip()


def build_breakout_message(data: dict) -> str:
    cur = data.get("currency", "USD")
    direction = "🚀 BULLISH" if "BULLISH" in data["breakout"] else "💥 BEARISH"
    return f"""
⚡ *BREAKOUT ALERT — {data['company']} ({data['ticker']})*

{direction} BREAKOUT DETECTED

💰 Current Price: {cur} {data['price']}
📊 RSI          : {data['rsi']}
📈 Volume       : {data['volume_info']['pct_change']:+.1f}% above average
🕯️ Candle       : {data['candle']}

🤖 AI Signal    : *{data['signal']}*

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (NPT)
""".strip()


def build_signal_message(data: dict) -> str:
    """General signal update message."""
    cur = data.get("currency", "USD")
    return f"""
📊 *SIGNAL UPDATE — {data['company']} ({data['ticker']})*

💰 Price  : {cur} {data['price']} ({data['change_pct']:+.2f}%)
🤖 Signal : *{data['signal']}*
📊 RSI    : {data['rsi']}
📈 MACD   : {data['macd']}
📉 EMA20  : {data['ema20']}

Reasons:
{chr(10).join('• ' + r for r in data['reasons'][:3])}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (NPT)
""".strip()


# ── WhatsApp sender ───────────────────────────────────────────────────────────

def send_whatsapp(message: str) -> bool:
    """
    Send a WhatsApp message via Twilio Sandbox.
    Returns True on success.
    """
    if not all([ACCOUNT_SID, AUTH_TOKEN, TO_NUMBER]):
        print("[ALERT] Twilio not configured — printing to console instead.")
        print("=" * 60)
        print(message)
        print("=" * 60)
        return False

    try:
        from twilio.rest import Client
        client = Client(ACCOUNT_SID, AUTH_TOKEN)
        msg = client.messages.create(
            from_=FROM_NUMBER,
            to=TO_NUMBER,
            body=message,
        )
        print(f"[WHATSAPP SENT] SID: {msg.sid}")
        return True
    except Exception as e:
        print(f"[WHATSAPP ERROR] {e}")
        # Fallback: print to console
        print(message)
        return False


# ── Main dispatch ─────────────────────────────────────────────────────────────

def dispatch_alert(data: dict, force: bool = False) -> bool:
    """
    Determine alert type, build the right message, and send it.
    Respects cooldown to avoid spamming.
    Returns True if alert was sent.
    """
    from database import log_alert  # avoid circular import at module level

    ticker     = data["ticker"]
    alert_type = data.get("alert_type")

    if not alert_type:
        return False

    # Cooldown check
    if not force and _within_cooldown(ticker, alert_type):
        print(f"[COOLDOWN] Skipping {alert_type} for {ticker} (cooldown active)")
        return False

    # Build message
    if alert_type == "BUY":
        msg = build_buy_message(data)
    elif alert_type == "SELL":
        msg = build_sell_message(data)
    elif alert_type == "STOP_LOSS":
        msg = build_stoploss_message(data)
    elif alert_type == "BREAKOUT":
        msg = build_breakout_message(data)
    else:
        msg = build_signal_message(data)

    # Send
    sent = send_whatsapp(msg)

    # Log to database
    log_alert(
        ticker=ticker,
        alert_type=alert_type,
        signal=data.get("signal", "—"),
        price=data.get("price", 0),
        message=msg,
        sent=sent,
    )

    if sent:
        _mark_sent(ticker, alert_type)

    return sent
