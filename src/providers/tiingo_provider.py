"""
Tiingo data provider.

Primary market-data source for non-demo tickers. Chosen over Alpha Vantage's
free tier because Tiingo's free plan returns adjusted close prices with full
history (back to 2018+) and a far higher daily quota (~1000 calls/day vs AV's
25/day), which is what makes arbitrary tickers viable in production.

All credentials are read from the environment — no keys are hardcoded.
Every successful response is cached (Postgres + file via providers.cache) so
repeat calls within the TTL window do not consume quota.

Environment variables
---------------------
TIINGO_API_KEY  Required. Your Tiingo API token.
"""

from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

from .cache import get_cache, set_cache

load_dotenv()

# ── constants ──────────────────────────────────────────────────────────────────
_TIINGO_BASE = "https://api.tiingo.com/tiingo/daily"
_PRICES_TTL = 86_400        # 24 h — refresh daily price data once per day
_REQUEST_TIMEOUT = 15       # seconds
_START_DATE = "2018-01-01"  # matches the processed dataset's history
# ──────────────────────────────────────────────────────────────────────────────


def _api_key() -> str | None:
    key = os.environ.get("TIINGO_API_KEY")
    return key.strip() if key else None


def _ok(data: Any, *, cached: bool = False) -> dict:
    return {"success": True, "data": data, "error": None, "message": None, "cached": cached}


def _err(error: str, message: str | None = None) -> dict:
    return {"success": False, "data": None, "error": error, "message": message, "cached": False}


def get_daily_prices(ticker: str) -> dict:
    """
    Fetch daily adjusted-close prices from Tiingo back to _START_DATE.

    Returns a result dict with keys:
      success (bool), data (list[dict]|None), error (str|None),
      message (str|None), cached (bool)

    On success, data is the raw Tiingo list of daily bars; each item contains
    at least "date" and "adjClose". Normalisation happens in the caller.

    Possible error values: missing_api_key, invalid_ticker, rate_limit,
    empty_response, network_error, api_error
    """
    t = ticker.upper().strip()
    cache_key = f"tiingo_prices_{t}"

    cached = get_cache(cache_key, ttl_seconds=_PRICES_TTL)
    if cached is not None:
        return _ok(cached, cached=True)

    api_key = _api_key()
    if not api_key:
        return _err("missing_api_key", "TIINGO_API_KEY is not set in environment")

    try:
        resp = requests.get(
            f"{_TIINGO_BASE}/{t}/prices",
            params={"startDate": _START_DATE, "token": api_key},
            headers={"Content-Type": "application/json"},
            timeout=_REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        return _err("network_error", "Tiingo request timed out")
    except requests.RequestException as exc:
        return _err("network_error", str(exc))

    # Tiingo signals errors with HTTP status codes + a JSON {"detail": "..."} body.
    if resp.status_code == 404:
        return _err("invalid_ticker", f"Tiingo has no data for {t}")
    if resp.status_code == 429:
        return _err("rate_limit", "Tiingo daily/hourly rate limit reached")
    if resp.status_code in (401, 403):
        return _err("api_error", "Tiingo rejected the API key (401/403)")
    if resp.status_code != 200:
        return _err("api_error", f"Tiingo returned HTTP {resp.status_code}")

    try:
        payload = resp.json()
    except ValueError:
        return _err("empty_response", "Tiingo returned a non-JSON response")

    if not isinstance(payload, list) or not payload:
        return _err("empty_response", f"Tiingo returned no price history for {t}")

    set_cache(cache_key, payload)
    return _ok(payload)
