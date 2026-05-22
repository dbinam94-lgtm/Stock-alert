"""
nepse_fetcher.py — Fetches live NEPSE stock data
Sources: Merolagani + Sharesansar (free, no API key needed)
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings("ignore")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def get_nepse_price(symbol: str) -> dict | None:
    """
    Fetch current price for a NEPSE stock from Merolagani.
    Returns dict with price, change_pct, volume etc.
    """
    symbol = symbol.upper().replace(".NP", "")

    # ── Try Merolagani first ──────────────────────────────────────────────────
    try:
        url  = f"https://merolagani.com/CompanyDetail.aspx?symbol={symbol}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Last traded price
        ltp_tag = soup.find("span", {"id": "ctl00_ContentPlaceHolder1_lblLTP"})
        chg_tag = soup.find("span", {"id": "ctl00_ContentPlaceHolder1_lblChange"})
        pct_tag = soup.find("span", {"id": "ctl00_ContentPlaceHolder1_lblPerChange"})
        vol_tag = soup.find("td", {"id": "ctl00_ContentPlaceHolder1_lblShareTraded"})

        if ltp_tag and ltp_tag.text.strip():
            price = float(ltp_tag.text.strip().replace(",", ""))
            chg   = float(chg_tag.text.strip().replace(",", "")) if chg_tag else 0
            pct   = float(pct_tag.text.strip().replace("%", "").replace(",", "")) if pct_tag else 0
            vol   = int(vol_tag.text.strip().replace(",", "")) if vol_tag else 0

            return {
                "price":      price,
                "prev_close": round(price - chg, 2),
                "change_pct": pct,
                "volume":     vol,
                "avg_volume": vol,
                "currency":   "NPR",
                "source":     "Merolagani",
            }
    except Exception as e:
        print(f"[MEROLAGANI ERROR] {symbol}: {e}")

    # ── Fallback: Sharesansar ─────────────────────────────────────────────────
    try:
        url  = f"https://www.sharesansar.com/company/{symbol.lower()}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        price_tag = soup.find("strong", {"id": "cur_rate"})
        if price_tag:
            price = float(price_tag.text.strip().replace(",", ""))
            return {
                "price":      price,
                "prev_close": price,
                "change_pct": 0,
                "volume":     0,
                "avg_volume": 0,
                "currency":   "NPR",
                "source":     "Sharesansar",
            }
    except Exception as e:
        print(f"[SHARESANSAR ERROR] {symbol}: {e}")

    return None


def get_nepse_history(symbol: str, days: int = 90) -> pd.DataFrame | None:
    """
    Fetch historical OHLCV data for a NEPSE stock from Merolagani.
    Returns a DataFrame or None.
    """
    symbol = symbol.upper().replace(".NP", "")
    try:
        url  = f"https://merolagani.com/handlers/TechnicalChartHandler.ashx?type=stock&symbol={symbol}&resolution=D&from=0&to=9999999999"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        data = resp.json()

        if "t" not in data or not data["t"]:
            return None

        df = pd.DataFrame({
            "Open":   data["o"],
            "High":   data["h"],
            "Low":    data["l"],
            "Close":  data["c"],
            "Volume": data["v"],
        }, index=pd.to_datetime(data["t"], unit="s"))

        df = df.tail(days)
        df.dropna(inplace=True)
        return df if len(df) >= 10 else None

    except Exception as e:
        print(f"[NEPSE HISTORY ERROR] {symbol}: {e}")
        return None


def is_nepse_ticker(ticker: str) -> bool:
    """Return True if ticker looks like a NEPSE stock."""
    ticker = ticker.upper()
    # NEPSE tickers end with .NP or are purely alphabetic (no dots, no .NS/.BO)
    if ticker.endswith(".NP"):
        return True
    if "." not in ticker and ticker.isalpha() and len(ticker) <= 10:
        return True
    return False
