"""
monitor.py — Background stock monitoring loop
Runs every N minutes, analyzes all watched stocks,
updates the price cache, and fires WhatsApp alerts.
"""

import time
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from database import get_watchlist, update_price_cache
from analyzer  import analyze_stock
from alerts    import dispatch_alert

# ── Logging setup ─────────────────────────────────────────────────────────────
LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "monitor.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),   # also print to terminal
    ],
)
log = logging.getLogger(__name__)

INTERVAL_MINUTES = int(os.getenv("MONITOR_INTERVAL_MINUTES", "5"))


# ── Core monitoring cycle ─────────────────────────────────────────────────────

def run_cycle():
    """
    One full monitoring cycle:
    1. Load watchlist from DB
    2. Analyze each stock
    3. Update price cache
    4. Fire alerts if conditions are met
    """
    stocks = get_watchlist()
    if not stocks:
        log.info("Watchlist is empty — nothing to monitor.")
        return

    log.info(f"=== Monitoring cycle started — {len(stocks)} stocks ===")

    for stock in stocks:
        ticker = stock["ticker"]
        log.info(f"Analyzing {ticker}...")

        try:
            result = analyze_stock(stock)
            if result is None:
                log.warning(f"No data for {ticker} — skipping.")
                continue

            # Update cache for dashboard
            update_price_cache(ticker, {
                "price":          result["price"],
                "change_pct":     result["change_pct"],
                "volume":         result["volume"],
                "rsi":            result["rsi"],
                "macd":           result["macd"],
                "signal_line":    result["signal_line"],
                "ema20":          result["ema20"],
                "ema50":          result["ema50"],
                "recommendation": result["signal"],
            })

            log.info(
                f"{ticker} | Price: {result['price']} | "
                f"Signal: {result['signal']} | Score: {result['score']}"
            )

            # Fire alert if needed
            if result.get("alert_type"):
                log.info(f"⚡ Alert triggered: {result['alert_type']} for {ticker}")
                dispatch_alert(result)

        except Exception as e:
            log.error(f"Error processing {ticker}: {e}", exc_info=True)

    log.info("=== Cycle complete ===\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def start_monitor():
    """
    Infinite loop — runs run_cycle() every INTERVAL_MINUTES.
    Safe to run in a background thread or as a standalone process.
    """
    log.info(f"Stock Monitor started. Interval: {INTERVAL_MINUTES} min.")
    while True:
        try:
            run_cycle()
        except KeyboardInterrupt:
            log.info("Monitor stopped by user.")
            break
        except Exception as e:
            log.error(f"Unexpected error in cycle: {e}", exc_info=True)
        
        log.info(f"Sleeping {INTERVAL_MINUTES} minute(s)...")
        time.sleep(INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    start_monitor()
