"""
Fetches last trading day closing price and daily % change via yfinance.
Cached per ticker in cache_prices.json, refreshed once per day.
"""

import json
import yfinance as yf
from datetime import date
from pathlib import Path

PRICE_CACHE = Path(__file__).parent / "cache_prices.json"


def get_price_info(ticker: str) -> dict:
    """
    Returns {"price": float, "change_pct": float} for the last completed
    trading day, or {"price": None, "change_pct": None} on failure.
    """
    today = str(date.today())
    cache = json.loads(PRICE_CACHE.read_text()) if PRICE_CACHE.exists() else {}

    if cache.get(ticker, {}).get("date") == today:
        return cache[ticker]

    try:
        hist = yf.Ticker(ticker).history(period="5d")
        if len(hist) >= 2:
            last_close = hist["Close"].iloc[-1]
            prev_close = hist["Close"].iloc[-2]
            result = {
                "date":       today,
                "price":      round(float(last_close), 2),
                "change_pct": round((last_close - prev_close) / prev_close, 6),
            }
        else:
            result = {"date": today, "price": None, "change_pct": None}
    except Exception:
        result = {"date": today, "price": None, "change_pct": None}

    cache[ticker] = result
    PRICE_CACHE.write_text(json.dumps(cache, indent=2))
    return result
