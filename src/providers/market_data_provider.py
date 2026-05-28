"""
Unified market data interface.

Read priority for company profiles
-----------------------------------
  0. Postgres companies table  — served if last_updated is within DB_TTL (24 h)
  1. Local AV JSON cache       — data/cache/av_overview_{TICKER}.json
  2. Alpha Vantage API         — primary live source
  3. yfinance                  — fallback for every AV error except invalid_ticker

Read priority for price history
---------------------------------
  1. Local AV JSON cache
  2. Alpha Vantage API
  3. yfinance

Write-back after any live fetch
---------------------------------
  • Postgres companies table   (upserted)
  • Local AV JSON cache        (handled inside alpha_vantage_provider)
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

from .alpha_vantage_provider import (
    get_company_overview,
    get_daily_prices,
)

logger = logging.getLogger(__name__)

# ── optional Postgres layer ────────────────────────────────────────────────────
# Providers may run without a database configured (e.g. CLI usage, tests).
# All DB calls are wrapped so any failure silently falls through.

_SRC = Path(__file__).parent.parent  # .../src/
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

try:
    import db as _db
    import db_repository as _repo
    _DB_IMPORT_OK = True
except ImportError:
    _DB_IMPORT_OK = False

_DB_TTL = timedelta(hours=24)
_AV_TICKER_INVALID = "invalid_ticker"


def _db_live() -> bool:
    """True if DATABASE_URL is set and importable."""
    return _DB_IMPORT_OK and _db.is_configured()


def _read_company_db(ticker: str) -> dict | None:
    """
    Return a fresh company row from Postgres, or None if:
      - DB not configured
      - ticker not found
      - last_updated is older than _DB_TTL
    """
    if not _db_live():
        return None
    try:
        row = _repo.get_company_from_db(ticker)
        if row is None:
            return None
        lu = row.get("last_updated")
        if lu is not None:
            if isinstance(lu, str):
                lu = datetime.fromisoformat(lu)
            if lu.tzinfo is None:
                lu = lu.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - lu > _DB_TTL:
                logger.debug("DB record for %s is stale — falling through", ticker)
                return None
        return row
    except Exception as exc:
        logger.warning("DB read failed for %s: %s", ticker, exc)
        return None


def _write_company_db(profile: dict) -> None:
    """Upsert company profile to Postgres; silently ignores any error."""
    if not _db_live():
        return
    try:
        _repo.upsert_company(profile)
        logger.debug("DB write: company %s", profile.get("ticker"))
    except Exception as exc:
        logger.warning("DB write failed for %s: %s", profile.get("ticker"), exc)


def _should_try_yfinance(av_error: str | None) -> bool:
    return av_error != _AV_TICKER_INVALID


# ── public API ─────────────────────────────────────────────────────────────────

def validate_ticker(ticker: str) -> dict:
    """
    Check whether *ticker* is a valid, recognised symbol.
    Returns {"valid": bool, "ticker": str, "source": str|None, "error": str|None}
    """
    t = ticker.upper().strip()

    av = get_company_overview(t)
    if av["success"]:
        return {
            "valid": True,
            "ticker": t,
            "source": "cache" if av["cached"] else "alpha_vantage",
            "error": None,
        }

    if _should_try_yfinance(av["error"]):
        try:
            info = yf.Ticker(t).info
            if info and info.get("symbol") == t:
                return {"valid": True, "ticker": t, "source": "yfinance", "error": None}
        except Exception:
            pass

    return {"valid": False, "ticker": t, "source": None, "error": av.get("message")}


def get_company_profile(ticker: str) -> dict:
    """
    Return a normalised company profile dict.

    Guaranteed fields (empty string when unknown):
      ticker, name, exchange, sector, industry, description, currency,
      market_cap, pe_ratio, week_52_high, week_52_low, dividend_yield,
      source, cached, error
    """
    t = ticker.upper().strip()

    def _empty(source: str | None, error: str | None) -> dict:
        return {
            "ticker": t, "name": "", "exchange": "", "sector": "",
            "industry": "", "description": "", "currency": "",
            "market_cap": "", "pe_ratio": "", "week_52_high": "",
            "week_52_low": "", "dividend_yield": "",
            "source": source, "cached": False, "error": error,
        }

    # ── Priority 0: Postgres ──────────────────────────────────────────────────
    db_row = _read_company_db(t)
    if db_row and db_row.get("name"):
        logger.debug("company_profile[DB]: %s", t)
        return {
            "ticker":        t,
            "name":          db_row.get("name", ""),
            "exchange":      db_row.get("exchange", ""),
            "sector":        db_row.get("sector", ""),
            "industry":      db_row.get("industry", ""),
            "description":   db_row.get("description", ""),
            "currency":      db_row.get("currency", ""),
            "market_cap":    db_row.get("market_cap", ""),
            "pe_ratio":      db_row.get("pe_ratio", ""),
            "week_52_high":  db_row.get("week_52_high", ""),
            "week_52_low":   db_row.get("week_52_low", ""),
            "dividend_yield": "",
            "source":        "database",
            "cached":        True,
            "error":         None,
        }

    # ── Priority 1 + 2: local AV cache → Alpha Vantage API ───────────────────
    av = get_company_overview(t)
    if av["success"]:
        raw = av["data"]
        profile = {
            "ticker":        t,
            "name":          raw.get("Name", ""),
            "exchange":      raw.get("Exchange", ""),
            "sector":        raw.get("Sector", ""),
            "industry":      raw.get("Industry", ""),
            "description":   raw.get("Description", ""),
            "currency":      raw.get("Currency", ""),
            "market_cap":    raw.get("MarketCapitalization", ""),
            "pe_ratio":      raw.get("PERatio", ""),
            "week_52_high":  raw.get("52WeekHigh", ""),
            "week_52_low":   raw.get("52WeekLow", ""),
            "dividend_yield": raw.get("DividendYield", ""),
            "source":        "cache" if av["cached"] else "alpha_vantage",
            "cached":        av["cached"],
            "error":         None,
        }
        # Write-back to Postgres if data came from the live API
        if not av["cached"]:
            _write_company_db(profile)
        return profile

    # ── Priority 3: yfinance fallback ─────────────────────────────────────────
    if _should_try_yfinance(av["error"]):
        try:
            info = yf.Ticker(t).info or {}
            if info.get("longName") or info.get("shortName"):
                profile = {
                    "ticker":        t,
                    "name":          info.get("longName") or info.get("shortName", ""),
                    "exchange":      info.get("exchange", ""),
                    "sector":        info.get("sector", ""),
                    "industry":      info.get("industry", ""),
                    "description":   info.get("longBusinessSummary", ""),
                    "currency":      info.get("currency", ""),
                    "market_cap":    str(info.get("marketCap", "")),
                    "pe_ratio":      str(info.get("trailingPE", "")),
                    "week_52_high":  str(info.get("fiftyTwoWeekHigh", "")),
                    "week_52_low":   str(info.get("fiftyTwoWeekLow", "")),
                    "dividend_yield": str(info.get("dividendYield", "")),
                    "source":        "yfinance",
                    "cached":        False,
                    "error":         None,
                }
                _write_company_db(profile)
                return profile
        except Exception as exc:
            return _empty("yfinance", str(exc))

    return _empty(None, av.get("message") or av.get("error"))


def get_price_history(ticker: str, days: int = 100) -> dict:
    """
    Return OHLCV price history as a list of dicts, newest entry first.

    Priority: local AV cache → Alpha Vantage API → yfinance.

    Returns
    -------
    {
      "ticker": str,
      "count": int,
      "prices": [{"date", "open", "high", "low", "close", "adjusted_close", "volume"}, ...],
      "source": "alpha_vantage" | "yfinance" | None,
      "cached": bool,
      "error": str | None,
    }
    """
    t = ticker.upper().strip()

    def _empty(error: str | None) -> dict:
        return {
            "ticker": t, "count": 0, "prices": [],
            "source": None, "cached": False, "error": error,
        }

    # ── Priority 1 + 2: local AV cache → Alpha Vantage ───────────────────────
    av = get_daily_prices(t)
    if av["success"]:
        ts: dict = av["data"].get("Time Series (Daily)", {})
        prices = []
        for date in sorted(ts.keys(), reverse=True)[:days]:
            row = ts[date]
            close = round(float(row["4. close"]), 4)
            prices.append({
                "date":           date,
                "open":           round(float(row["1. open"]), 4),
                "high":           round(float(row["2. high"]), 4),
                "low":            round(float(row["3. low"]), 4),
                "close":          close,
                "adjusted_close": close,
                "volume":         int(row["5. volume"]),
            })
        return {
            "ticker": t,
            "count":  len(prices),
            "prices": prices,
            "source": "cache" if av["cached"] else "alpha_vantage",
            "cached": av["cached"],
            "error":  None,
        }

    # ── Priority 3: yfinance fallback ─────────────────────────────────────────
    if _should_try_yfinance(av["error"]):
        yf_period = "1y" if days > 90 else ("3mo" if days > 30 else "1mo")
        try:
            hist = yf.Ticker(t).history(period=yf_period)
            if not hist.empty:
                prices = [
                    {
                        "date":           date.strftime("%Y-%m-%d"),
                        "open":           round(float(row["Open"]), 4),
                        "high":           round(float(row["High"]), 4),
                        "low":            round(float(row["Low"]), 4),
                        "close":          round(float(row["Close"]), 4),
                        "adjusted_close": round(float(row["Close"]), 4),
                        "volume":         int(row["Volume"]),
                    }
                    for date, row in hist.iloc[::-1].iterrows()
                ][:days]
                return {
                    "ticker": t,
                    "count":  len(prices),
                    "prices": prices,
                    "source": "yfinance",
                    "cached": False,
                    "error":  None,
                }
        except Exception as exc:
            return _empty(str(exc))

    return _empty(av.get("message") or av.get("error"))
