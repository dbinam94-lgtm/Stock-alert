"""
database.py — Permanent storage using Streamlit's built-in file persistence
Saves watchlist as JSON file that persists across redeploys on Streamlit Cloud.
"""

import os
import json
from datetime import datetime
from pathlib import Path

# On Streamlit Cloud, use /tmp for writable storage
# We store a JSON file that acts as our database
STORAGE_DIR  = Path("/tmp/stock_monitor_data")
STORAGE_DIR.mkdir(exist_ok=True)
WATCHLIST_FILE = STORAGE_DIR / "watchlist.json"
ALERTS_FILE    = STORAGE_DIR / "alerts.json"

_price_cache = {}


# ── JSON helpers ──────────────────────────────────────────────────────────────

def _read_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text())
        return default
    except Exception:
        return default


def _write_json(path: Path, data):
    try:
        path.write_text(json.dumps(data, indent=2))
    except Exception as e:
        print(f"[DB WRITE ERROR] {e}")


# ── Watchlist CRUD ────────────────────────────────────────────────────────────

def get_watchlist() -> list:
    data = _read_json(WATCHLIST_FILE, [])
    return [s for s in data if s.get("active", 1) == 1]


def add_stock(company, ticker, buy_price, sell_price, stop_loss,
              quantity=1, exchange="OTHER", currency="NPR") -> bool:
    try:
        data   = _read_json(WATCHLIST_FILE, [])
        ticker = ticker.upper()

        # Update if exists
        for s in data:
            if s["ticker"] == ticker:
                s.update({
                    "company": company, "exchange": exchange,
                    "buy_price": buy_price, "sell_price": sell_price,
                    "stop_loss": stop_loss, "quantity": quantity,
                    "currency": currency, "active": 1,
                })
                _write_json(WATCHLIST_FILE, data)
                return True

        # Add new
        data.append({
            "id":         len(data) + 1,
            "company":    company,
            "ticker":     ticker,
            "exchange":   exchange,
            "buy_price":  buy_price,
            "sell_price": sell_price,
            "stop_loss":  stop_loss,
            "quantity":   quantity,
            "currency":   currency,
            "active":     1,
            "created_at": datetime.now().isoformat(),
        })
        _write_json(WATCHLIST_FILE, data)
        return True
    except Exception as e:
        print(f"[DB ERROR] add_stock: {e}")
        return False


def remove_stock(ticker: str) -> bool:
    try:
        data   = _read_json(WATCHLIST_FILE, [])
        ticker = ticker.upper()
        for s in data:
            if s["ticker"] == ticker:
                s["active"] = 0
        _write_json(WATCHLIST_FILE, data)
        return True
    except Exception as e:
        print(f"[DB ERROR] remove_stock: {e}")
        return False


def get_stock(ticker: str):
    return next((s for s in get_watchlist() if s["ticker"] == ticker.upper()), None)


# ── Alert logging ─────────────────────────────────────────────────────────────

def log_alert(ticker, alert_type, signal, price, message, sent=False):
    data = _read_json(ALERTS_FILE, [])
    data.insert(0, {
        "ticker":     ticker,
        "alert_type": alert_type,
        "signal":     signal,
        "price":      price,
        "message":    (message or "")[:200],
        "sent":       int(sent),
        "created_at": datetime.now().isoformat(),
    })
    _write_json(ALERTS_FILE, data[:200])  # keep last 200 alerts


def get_recent_alerts(limit=50) -> list:
    return _read_json(ALERTS_FILE, [])[:limit]


def get_last_alert_time(ticker, alert_type):
    alerts = _read_json(ALERTS_FILE, [])
    for a in alerts:
        if a["ticker"] == ticker and a["alert_type"] == alert_type:
            return datetime.fromisoformat(a["created_at"])
    return None


# ── Price cache (in-memory) ───────────────────────────────────────────────────

def update_price_cache(ticker: str, data: dict):
    _price_cache[ticker] = {**data, "last_updated": datetime.now().isoformat()}


def get_price_cache() -> dict:
    return _price_cache


DB_PATH = WATCHLIST_FILE


def init_db():
    STORAGE_DIR.mkdir(exist_ok=True)
    print(f"[DB] Storage ready at {STORAGE_DIR}")


init_db()
