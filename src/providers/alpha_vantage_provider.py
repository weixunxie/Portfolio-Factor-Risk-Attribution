"""
Alpha Vantage data provider.

All API credentials are read from environment variables — no keys are hardcoded.

Quota protection: every successful API response is written to the local cache
(data/cache/) so repeat calls within the TTL window hit the cache, not the API.
Free-tier users have 25 calls/day; caching keeps this from being exhausted.

Environment variables
---------------------
ALPHA_VANTAGE_API_KEY  Required. Your Alpha Vantage API key.
"""

import os
from typing import Any

import requests
from dotenv import load_dotenv

from .cache import cache_exists, get_cache, set_cache

load_dotenv()

# ── constants ──────────────────────────────────────────────────────────────────
_AV_BASE = "https://www.alphavantage.co/query"
_OVERVIEW_TTL = 86_400       # 24 h — company profile changes rarely
_PRICES_TTL = 86_400         # 24 h — refresh daily price data once per day
_REQUEST_TIMEOUT = 12        # seconds
# ──────────────────────────────────────────────────────────────────────────────


def _api_key() -> str | None:
    return os.environ.get("ALPHA_VANTAGE_API_KEY")


def _ok(data: Any, *, cached: bool = False) -> dict:
    return {"success": True, "data": data, "error": None, "message": None, "cached": cached}


def _err(error: str, message: str | None = None) -> dict:
    return {"success": False, "data": None, "error": error, "message": message, "cached": False}


def _detect_api_error(payload: dict) -> str | None:
    """
    Detect Alpha Vantage soft errors that still return HTTP 200.
    Returns an error-type string if found, else None.
    """
    if "Note" in payload:
        return "rate_limit"
    if "Information" in payload:
        # Could be either a rate-limit notice or an invalid endpoint notice.
        msg = payload["Information"]
        if "call frequency" in msg.lower() or "api key" in msg.lower():
            return "rate_limit"
        return "api_error"
    if "Error Message" in payload:
        return "invalid_ticker"
    return None


def get_company_overview(ticker: str) -> dict:
    """
    Fetch company overview from Alpha Vantage OVERVIEW endpoint.

    Returns a result dict with keys:
      success (bool), data (dict|None), error (str|None),
      message (str|None), cached (bool)

    Possible error values: missing_api_key, rate_limit, invalid_ticker,
    empty_response, network_error, api_error
    """
    t = ticker.upper().strip()
    cache_key = f"av_overview_{t}"

    cached = get_cache(cache_key, ttl_seconds=_OVERVIEW_TTL)
    if cached is not None:
        return _ok(cached, cached=True)

    api_key = _api_key()
    if not api_key:
        return _err("missing_api_key", "ALPHA_VANTAGE_API_KEY is not set in environment")

    try:
        resp = requests.get(
            _AV_BASE,
            params={"function": "OVERVIEW", "symbol": t, "apikey": api_key},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.exceptions.Timeout:
        return _err("network_error", "Alpha Vantage request timed out")
    except requests.RequestException as exc:
        return _err("network_error", str(exc))

    error_type = _detect_api_error(payload)
    if error_type:
        msg = payload.get("Note") or payload.get("Information") or payload.get("Error Message")
        return _err(error_type, msg)

    if not payload or "Symbol" not in payload:
        return _err("empty_response", "Alpha Vantage returned an empty overview response")

    set_cache(cache_key, payload)
    return _ok(payload)


def get_daily_prices(ticker: str) -> dict:
    """
    Fetch the last ~100 trading days of daily OHLCV prices from Alpha Vantage.

    Uses the free-tier TIME_SERIES_DAILY endpoint (not the premium
    TIME_SERIES_DAILY_ADJUSTED endpoint).  The response fields are:
      "1. open", "2. high", "3. low", "4. close", "5. volume"

    Returns a result dict with keys:
      success (bool), data (dict|None), error (str|None),
      message (str|None), cached (bool)

    The raw Alpha Vantage response is cached as-is; normalisation happens in
    market_data_provider.get_price_history().
    """
    t = ticker.upper().strip()
    cache_key = f"av_prices_{t}"

    cached = get_cache(cache_key, ttl_seconds=_PRICES_TTL)
    if cached is not None:
        return _ok(cached, cached=True)

    api_key = _api_key()
    if not api_key:
        return _err("missing_api_key", "ALPHA_VANTAGE_API_KEY is not set in environment")

    try:
        resp = requests.get(
            _AV_BASE,
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": t,
                "outputsize": "compact",   # last 100 trading days
                "apikey": api_key,
            },
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.exceptions.Timeout:
        return _err("network_error", "Alpha Vantage request timed out")
    except requests.RequestException as exc:
        return _err("network_error", str(exc))

    error_type = _detect_api_error(payload)
    if error_type:
        msg = payload.get("Note") or payload.get("Information") or payload.get("Error Message")
        return _err(error_type, msg)

    if "Time Series (Daily)" not in payload:
        return _err("empty_response", "Alpha Vantage returned no price time series")

    set_cache(cache_key, payload)
    return _ok(payload)
