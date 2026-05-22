"""
analyzer.py — Technical analysis engine
Calculates RSI, MACD, EMA, Support/Resistance, Volume analysis,
Breakout detection, and generates a final AI signal.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

from nepse_fetcher import get_nepse_price, get_nepse_history, is_nepse_ticker


# ── Data fetcher ──────────────────────────────────────────────────────────────

def fetch_data(ticker: str, period: str = "3mo", interval: str = "1d") -> pd.DataFrame | None:
    """
    Fetch OHLCV data — auto-detects NEPSE vs global stocks.
    Returns a cleaned DataFrame or None on failure.
    """
    # NEPSE stocks
    if is_nepse_ticker(ticker):
        return get_nepse_history(ticker.replace(".NP", ""), days=90)

    # Global stocks via yfinance
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df.empty:
            return None
        df.index = pd.to_datetime(df.index)
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.dropna(inplace=True)
        return df
    except Exception as e:
        print(f"[FETCH ERROR] {ticker}: {e}")
        return None


def get_current_price(ticker: str) -> dict | None:
    """Get the latest price — auto-detects NEPSE vs global."""

    # NEPSE stocks
    if is_nepse_ticker(ticker):
        return get_nepse_price(ticker)

    # Global stocks via yfinance
    try:
        stock = yf.Ticker(ticker)
        info  = stock.fast_info
        price = round(float(info.last_price), 4)
        prev  = round(float(info.previous_close), 4)
        chg   = round(((price - prev) / prev) * 100, 2) if prev else 0
        vol   = int(info.three_month_average_volume or 0)
        return {
            "price":      price,
            "prev_close": prev,
            "change_pct": chg,
            "volume":     int(info.last_volume or 0),
            "avg_volume": vol,
            "currency":   getattr(info, "currency", "USD"),
        }
    except Exception as e:
        print(f"[PRICE ERROR] {ticker}: {e}")
        return None


# ── Indicator calculations ────────────────────────────────────────────────────

def calc_rsi(closes: pd.Series, period: int = 14) -> float:
    """Relative Strength Index."""
    delta = closes.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    rsi   = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


def calc_macd(closes: pd.Series):
    """MACD line, signal line, and histogram."""
    ema12  = closes.ewm(span=12, adjust=False).mean()
    ema26  = closes.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist   = macd - signal
    return (
        round(float(macd.iloc[-1]),   4),
        round(float(signal.iloc[-1]), 4),
        round(float(hist.iloc[-1]),   4),
    )


def calc_ema(closes: pd.Series, period: int) -> float:
    return round(float(closes.ewm(span=period, adjust=False).mean().iloc[-1]), 4)


def calc_support_resistance(df: pd.DataFrame, window: int = 20):
    """Simple pivot-based support and resistance."""
    highs  = df["High"].rolling(window).max()
    lows   = df["Low"].rolling(window).min()
    recent = df.tail(window)
    resistance = round(float(highs.iloc[-1]), 4)
    support    = round(float(lows.iloc[-1]),  4)
    return support, resistance


def detect_breakout(df: pd.DataFrame, window: int = 20) -> str:
    """
    Returns 'BULLISH_BREAKOUT', 'BEARISH_BREAKOUT', or 'NO_BREAKOUT'.
    """
    if len(df) < window + 2:
        return "NO_BREAKOUT"

    recent_close  = df["Close"].iloc[-1]
    prev_close    = df["Close"].iloc[-2]
    resistance    = df["High"].iloc[-window-1:-1].max()
    support       = df["Low"].iloc[-window-1:-1].min()
    avg_vol       = df["Volume"].iloc[-window-1:-1].mean()
    recent_vol    = df["Volume"].iloc[-1]
    vol_spike     = recent_vol > avg_vol * 1.5

    if recent_close > resistance and vol_spike:
        return "BULLISH_BREAKOUT"
    elif recent_close < support and vol_spike:
        return "BEARISH_BREAKOUT"
    return "NO_BREAKOUT"


def candlestick_pattern(df: pd.DataFrame) -> str:
    """Detect the last candlestick pattern."""
    if len(df) < 3:
        return "NEUTRAL"

    o, h, l, c = (df["Open"].iloc[-1], df["High"].iloc[-1],
                  df["Low"].iloc[-1],  df["Close"].iloc[-1])
    body  = abs(c - o)
    upper = h - max(c, o)
    lower = min(c, o) - l
    total = h - l if (h - l) > 0 else 0.0001

    # Doji — tiny body
    if body / total < 0.1:
        return "DOJI (Indecision)"
    # Hammer / Hanging Man
    if lower > body * 2 and upper < body * 0.5:
        return "HAMMER (Bullish reversal)" if c > o else "HANGING_MAN (Bearish)"
    # Bullish / Bearish Engulfing
    prev_body = df["Close"].iloc[-2] - df["Open"].iloc[-2]
    curr_body = c - o
    if curr_body > 0 and prev_body < 0 and abs(curr_body) > abs(prev_body):
        return "BULLISH_ENGULFING"
    if curr_body < 0 and prev_body > 0 and abs(curr_body) > abs(prev_body):
        return "BEARISH_ENGULFING"
    # Shooting Star
    if upper > body * 2 and lower < body * 0.5 and c < o:
        return "SHOOTING_STAR (Bearish)"
    return "NEUTRAL"


def volume_analysis(df: pd.DataFrame, window: int = 20) -> dict:
    avg_vol    = df["Volume"].iloc[-window:].mean()
    last_vol   = df["Volume"].iloc[-1]
    pct_change = round(((last_vol - avg_vol) / avg_vol) * 100, 1) if avg_vol else 0
    trend      = "ABOVE_AVERAGE" if last_vol > avg_vol * 1.2 else (
                 "BELOW_AVERAGE" if last_vol < avg_vol * 0.8 else "AVERAGE")
    return {"current": int(last_vol), "average": int(avg_vol),
            "pct_change": pct_change, "trend": trend}


# ── AI Signal engine ──────────────────────────────────────────────────────────

def generate_signal(rsi: float, macd: float, signal_line: float,
                    price: float, ema20: float, ema50: float,
                    breakout: str, candle: str, vol: dict,
                    buy_price: float, sell_price: float, stop_loss: float) -> dict:
    """
    Combines all indicators into a weighted score.
    Score > 0 = bullish, < 0 = bearish.
    Returns a dict with signal, score, and explanation.
    """
    score  = 0
    reasons = []

    # ── RSI ──────────────────────────────────────────────────
    if rsi < 30:
        score += 2;  reasons.append(f"RSI={rsi} → Oversold (Bullish)")
    elif rsi < 45:
        score += 1;  reasons.append(f"RSI={rsi} → Approaching oversold")
    elif rsi > 70:
        score -= 2;  reasons.append(f"RSI={rsi} → Overbought (Bearish)")
    elif rsi > 55:
        score -= 1;  reasons.append(f"RSI={rsi} → Approaching overbought")
    else:
        reasons.append(f"RSI={rsi} → Neutral")

    # ── MACD ─────────────────────────────────────────────────
    if macd > signal_line:
        score += 1;  reasons.append("MACD above signal → Bullish momentum")
    else:
        score -= 1;  reasons.append("MACD below signal → Bearish momentum")

    # MACD histogram direction (momentum acceleration)
    if macd > 0:
        score += 1;  reasons.append("MACD positive → Uptrend")
    else:
        score -= 1;  reasons.append("MACD negative → Downtrend")

    # ── EMA Trend ────────────────────────────────────────────
    if price > ema20 > ema50:
        score += 2;  reasons.append("Price > EMA20 > EMA50 → Strong uptrend")
    elif price > ema20:
        score += 1;  reasons.append("Price > EMA20 → Short-term bullish")
    elif price < ema20 < ema50:
        score -= 2;  reasons.append("Price < EMA20 < EMA50 → Strong downtrend")
    elif price < ema20:
        score -= 1;  reasons.append("Price < EMA20 → Short-term bearish")

    # ── Breakout ─────────────────────────────────────────────
    if breakout == "BULLISH_BREAKOUT":
        score += 2;  reasons.append("⚡ Bullish breakout detected!")
    elif breakout == "BEARISH_BREAKOUT":
        score -= 2;  reasons.append("⚡ Bearish breakdown detected!")

    # ── Candlestick ──────────────────────────────────────────
    if "BULLISH" in candle or "HAMMER" in candle:
        score += 1;  reasons.append(f"Candle: {candle}")
    elif "BEARISH" in candle or "SHOOTING" in candle or "HANGING" in candle:
        score -= 1;  reasons.append(f"Candle: {candle}")

    # ── Volume confirmation ──────────────────────────────────
    if vol["trend"] == "ABOVE_AVERAGE":
        reasons.append(f"Volume +{vol['pct_change']}% above avg → Confirms move")
        if score > 0: score += 1
        else:         score -= 1
    elif vol["trend"] == "BELOW_AVERAGE":
        reasons.append("Low volume → Weak conviction")

    # ── Price vs targets ─────────────────────────────────────
    if price <= buy_price * 1.005:
        score += 1;  reasons.append(f"Price at BUY zone (target ${buy_price})")
    if price >= sell_price * 0.995:
        score -= 1;  reasons.append(f"Price at SELL zone (target ${sell_price})")
    if price <= stop_loss * 1.01:
        score -= 3;  reasons.append(f"⛔ NEAR STOP-LOSS (${stop_loss})!")

    # ── Convert score to signal ───────────────────────────────
    if   score >= 5:  signal = "STRONG BUY  ✅"
    elif score >= 2:  signal = "BUY  📈"
    elif score >= -1: signal = "HOLD  ⏸️"
    elif score >= -4: signal = "SELL  📉"
    else:             signal = "STRONG SELL  🔴"

    return {
        "signal":  signal,
        "score":   score,
        "reasons": reasons,
    }


# ── Main analysis function ────────────────────────────────────────────────────

def analyze_stock(stock_info: dict) -> dict | None:
    """
    Full analysis for one stock.
    stock_info must have: ticker, buy_price, sell_price, stop_loss
    Returns a rich analysis dict or None on data failure.
    """
    ticker     = stock_info["ticker"]
    buy_price  = float(stock_info["buy_price"])
    sell_price = float(stock_info["sell_price"])
    stop_loss  = float(stock_info["stop_loss"])

    # 1 — Fetch data
    df = fetch_data(ticker, period="3mo", interval="1d")
    if df is None or len(df) < 30:
        return None

    price_data = get_current_price(ticker)
    if price_data is None:
        return None

    closes = df["Close"]
    price  = price_data["price"]

    # 2 — Indicators
    rsi         = calc_rsi(closes)
    macd, sig, hist = calc_macd(closes)
    ema20       = calc_ema(closes, 20)
    ema50       = calc_ema(closes, 50)
    ema200      = calc_ema(closes, 200) if len(closes) >= 200 else None
    support, resistance = calc_support_resistance(df)
    breakout    = detect_breakout(df)
    candle      = candlestick_pattern(df)
    vol         = volume_analysis(df)

    # 3 — AI Signal
    sig_result  = generate_signal(
        rsi, macd, sig, price, ema20, ema50,
        breakout, candle, vol,
        buy_price, sell_price, stop_loss
    )

    # 4 — Alert type
    alert_type = None
    if price <= buy_price * 1.01:
        alert_type = "BUY"
    elif price >= sell_price * 0.99:
        alert_type = "SELL"
    elif price <= stop_loss * 1.02:
        alert_type = "STOP_LOSS"
    elif breakout != "NO_BREAKOUT":
        alert_type = "BREAKOUT"

    # 5 — P&L estimate
    qty       = float(stock_info.get("quantity", 1))
    cost      = buy_price * qty
    current   = price * qty
    potential_profit = round((sell_price - buy_price) * qty, 2)
    unrealized_pnl   = round((price - buy_price) * qty, 2)

    return {
        "ticker":      ticker,
        "company":     stock_info.get("company", ticker),
        "price":       price,
        "change_pct":  price_data["change_pct"],
        "volume":      price_data["volume"],
        "avg_volume":  price_data["avg_volume"],
        "currency":    price_data["currency"],

        # Indicators
        "rsi":         rsi,
        "macd":        macd,
        "signal_line": sig,
        "macd_hist":   hist,
        "ema20":       ema20,
        "ema50":       ema50,
        "ema200":      ema200,
        "support":     support,
        "resistance":  resistance,
        "breakout":    breakout,
        "candle":      candle,
        "volume_info": vol,

        # Targets
        "buy_price":   buy_price,
        "sell_price":  sell_price,
        "stop_loss":   stop_loss,

        # AI Decision
        "signal":      sig_result["signal"],
        "score":       sig_result["score"],
        "reasons":     sig_result["reasons"],

        # Alert
        "alert_type":  alert_type,

        # P&L
        "qty":               qty,
        "potential_profit":  potential_profit,
        "unrealized_pnl":    unrealized_pnl,

        "timestamp": datetime.now().isoformat(),
    }
