"""
nepse_fetcher.py — Fetches NEPSE stock data from Merolagani and Sharesansar
Works during and after market hours (shows LTP - Last Transaction Price)
"""

import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings("ignore")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def get_nepse_price(symbol: str) -> dict | None:
    symbol = symbol.upper().replace(".NP", "")

    # ── Try Merolagani ────────────────────────────────────────────────────────
    try:
        url  = f"https://merolagani.com/CompanyDetail.aspx?symbol={symbol}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        # LTP
        ltp_tag = soup.find("span", {"id": "ctl00_ContentPlaceHolder1_lblLTP"})
        chg_tag = soup.find("span", {"id": "ctl00_ContentPlaceHolder1_lblChange"})
        pct_tag = soup.find("span", {"id": "ctl00_ContentPlaceHolder1_lblPerChange"})
        vol_tag = soup.find("td",   {"id": "ctl00_ContentPlaceHolder1_lblShareTraded"})
        high_tag= soup.find("td",   {"id": "ctl00_ContentPlaceHolder1_lblHigh"})
        low_tag = soup.find("td",   {"id": "ctl00_ContentPlaceHolder1_lblLow"})
        open_tag= soup.find("td",   {"id": "ctl00_ContentPlaceHolder1_lblOpen"})
        prev_tag= soup.find("td",   {"id": "ctl00_ContentPlaceHolder1_lblPrevClose"})

        def clean(tag):
            return tag.text.strip().replace(",", "") if tag else "0"

        if ltp_tag and ltp_tag.text.strip():
            price = float(clean(ltp_tag))
            chg   = float(clean(chg_tag))   if chg_tag else 0
            pct   = float(clean(pct_tag).replace("%","")) if pct_tag else 0
            vol   = int(float(clean(vol_tag)))   if vol_tag else 0
            high  = float(clean(high_tag))  if high_tag else price
            low   = float(clean(low_tag))   if low_tag  else price
            open_ = float(clean(open_tag))  if open_tag else price
            prev  = float(clean(prev_tag))  if prev_tag else price

            return {
                "price":      price,
                "prev_close": prev,
                "change_pct": pct,
                "change":     chg,
                "volume":     vol,
                "avg_volume": vol,
                "high":       high,
                "low":        low,
                "open":       open_,
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
        prev_tag  = soup.find("td",     {"id": "prev_close"})

        if price_tag:
            price = float(price_tag.text.strip().replace(",", ""))
            prev  = float(prev_tag.text.strip().replace(",", "")) if prev_tag else price
            pct   = round(((price - prev) / prev) * 100, 2) if prev else 0
            return {
                "price":      price,
                "prev_close": prev,
                "change_pct": pct,
                "volume":     0,
                "avg_volume": 0,
                "currency":   "NPR",
                "source":     "Sharesansar",
            }
    except Exception as e:
        print(f"[SHARESANSAR ERROR] {symbol}: {e}")

    return None


def get_nepse_history(symbol: str, days: int = 90) -> pd.DataFrame | None:
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
    ticker = ticker.upper()
    if ticker.endswith(".NP"):
        return True
    if "." not in ticker and ticker.isalpha() and len(ticker) <= 10:
        return True
    return False
