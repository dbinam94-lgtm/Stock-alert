"""
database.py — SQLite database setup and CRUD operations
Uses SQLAlchemy ORM for clean, safe database access
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "stocks.db"
DB_PATH.parent.mkdir(exist_ok=True)


def get_connection():
    """Return a raw SQLite connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row   # allows dict-style access
    return conn


def init_db():
    """Create all tables if they don't already exist."""
    conn = get_connection()
    c = conn.cursor()

    # ── Watchlist ─────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company     TEXT    NOT NULL,
            ticker      TEXT    NOT NULL UNIQUE,
            exchange    TEXT    DEFAULT 'NASDAQ',
            buy_price   REAL    NOT NULL,
            sell_price  REAL    NOT NULL,
            stop_loss   REAL    NOT NULL,
            quantity    REAL    DEFAULT 1,
            currency    TEXT    DEFAULT 'USD',
            active      INTEGER DEFAULT 1,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── Alert history ──────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT    NOT NULL,
            alert_type  TEXT    NOT NULL,   -- BUY / SELL / STOP_LOSS / SIGNAL
            signal      TEXT    NOT NULL,   -- STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL
            price       REAL    NOT NULL,
            message     TEXT,
            sent        INTEGER DEFAULT 0,  -- 1 = WhatsApp sent successfully
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── Price cache ────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS price_cache (
            ticker      TEXT    PRIMARY KEY,
            price       REAL,
            change_pct  REAL,
            volume      INTEGER,
            rsi         REAL,
            macd        REAL,
            signal_line REAL,
            ema20       REAL,
            ema50       REAL,
            recommendation TEXT,
            last_updated TEXT
        )
    """)

    conn.commit()
    conn.close()


# ── Watchlist CRUD ────────────────────────────────────────────────────────────

def add_stock(company, ticker, buy_price, sell_price, stop_loss,
              quantity=1, exchange="NASDAQ", currency="USD"):
    """Add a new stock to the watchlist. Returns True on success."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO watchlist (company, ticker, exchange, buy_price, sell_price,
                                   stop_loss, quantity, currency)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (company, ticker.upper(), exchange, buy_price, sell_price,
              stop_loss, quantity, currency))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Ticker already exists — update instead
        conn.execute("""
            UPDATE watchlist
            SET company=?, exchange=?, buy_price=?, sell_price=?,
                stop_loss=?, quantity=?, currency=?, active=1
            WHERE ticker=?
        """, (company, exchange, buy_price, sell_price, stop_loss,
              quantity, currency, ticker.upper()))
        conn.commit()
        return True
    finally:
        conn.close()


def remove_stock(ticker):
    """Soft-delete a stock from watchlist."""
    conn = get_connection()
    conn.execute("UPDATE watchlist SET active=0 WHERE ticker=?", (ticker.upper(),))
    conn.commit()
    conn.close()


def get_watchlist():
    """Return all active stocks as a list of dicts."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM watchlist WHERE active=1 ORDER BY company"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stock(ticker):
    """Return a single stock dict or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM watchlist WHERE ticker=? AND active=1", (ticker.upper(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Alert CRUD ────────────────────────────────────────────────────────────────

def log_alert(ticker, alert_type, signal, price, message, sent=False):
    conn = get_connection()
    conn.execute("""
        INSERT INTO alerts (ticker, alert_type, signal, price, message, sent)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (ticker, alert_type, signal, price, message, int(sent)))
    conn.commit()
    conn.close()


def get_recent_alerts(limit=50):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_last_alert_time(ticker, alert_type):
    """Returns datetime of the last alert of this type for ticker, or None."""
    conn = get_connection()
    row = conn.execute("""
        SELECT created_at FROM alerts
        WHERE ticker=? AND alert_type=?
        ORDER BY created_at DESC LIMIT 1
    """, (ticker, alert_type)).fetchone()
    conn.close()
    if row:
        return datetime.fromisoformat(row["created_at"])
    return None


# ── Price cache ───────────────────────────────────────────────────────────────

def update_price_cache(ticker, data: dict):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO price_cache
            (ticker, price, change_pct, volume, rsi, macd, signal_line,
             ema20, ema50, recommendation, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker,
        data.get("price"),
        data.get("change_pct"),
        data.get("volume"),
        data.get("rsi"),
        data.get("macd"),
        data.get("signal_line"),
        data.get("ema20"),
        data.get("ema50"),
        data.get("recommendation"),
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()


def get_price_cache():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM price_cache").fetchall()
    conn.close()
    return {r["ticker"]: dict(r) for r in rows}


# Initialise on import
init_db()
