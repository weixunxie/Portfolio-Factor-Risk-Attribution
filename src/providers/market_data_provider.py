"""
Unified market data interface.

Priority order for every data type:
  1. Local file cache (data/cache/) — always checked first
  2. Alpha Vantage API — primary live source
  3. yfinance — fallback whenever Alpha Vantage cannot return usable data,
     EXCEPT when Alpha Vantage explicitly confirms the ticker is invalid
     (in that case yfinance would also fail, so we skip it)

This means yfinance kicks in for: rate limits, missing API key, network errors,
premium-endpoint restrictions, or any other non-ticker error from Alpha Vantage.
"""

from __future__ import annotations

import yfinance as yf

from .alpha_vantage_provider import (
    get_company_overview,
    get_daily_prices,
)

# The only error type that means "the ticker itself is wrong" — skip yfinance.
# Every other AV error (rate_limit, missing_api_key, network_error,
# api_error, empty_response) should fall through to yfinance.
_AV_TICKER_INVALID = "invalid_ticker"


def _should_try_yfinance(av_error: str | None) -> bool:
    return av_error != _AV_TICKER_INVALID


def validate_ticker(ticker: str) -> dict:
    """
    Check whether *ticker* is a valid, recognised symbol.

    Returns
    -------
    {"valid": bool, "ticker": str, "source": str|None, "error": str|None}
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

    Fields guaranteed to be present (value may be empty string if unknown):
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

    av = get_company_overview(t)
    if av["success"]:
        raw = av["data"]
        return {
            "ticker": t,
            "name": raw.get("Name", ""),
            "exchange": raw.get("Exchange", ""),
            "sector": raw.get("Sector", ""),
            "industry": raw.get("Industry", ""),
            "description": raw.get("Description", ""),
            "currency": raw.get("Currency", ""),
            "market_cap": raw.get("MarketCapitalization", ""),
            "pe_ratio": raw.get("PERatio", ""),
            "week_52_high": raw.get("52WeekHigh", ""),
            "week_52_low": raw.get("52WeekLow", ""),
            "dividend_yield": raw.get("DividendYield", ""),
            "source": "cache" if av["cached"] else "alpha_vantage",
            "cached": av["cached"],
            "error": None,
        }

    if _should_try_yfinance(av["error"]):
        try:
            info = yf.Ticker(t).info or {}
            if info.get("longName") or info.get("shortName"):
                return {
                    "ticker": t,
                    "name": info.get("longName") or info.get("shortName", ""),
                    "exchange": info.get("exchange", ""),
                    "sector": info.get("sector", ""),
                    "industry": info.get("industry", ""),
                    "description": info.get("longBusinessSummary", ""),
                    "currency": info.get("currency", ""),
                    "market_cap": str(info.get("marketCap", "")),
                    "pe_ratio": str(info.get("trailingPE", "")),
                    "week_52_high": str(info.get("fiftyTwoWeekHigh", "")),
                    "week_52_low": str(info.get("fiftyTwoWeekLow", "")),
                    "dividend_yield": str(info.get("dividendYield", "")),
                    "source": "yfinance",
                    "cached": False,
                    "error": None,
                }
        except Exception as exc:
            return _empty("yfinance", str(exc))

    return _empty(None, av.get("message") or av.get("error"))


def get_price_history(ticker: str, days: int = 100) -> dict:
    """
    Return OHLCV price history as a list of dicts, newest entry first.

    Parameters
    ----------
    ticker : ticker symbol
    days   : maximum number of trading days to return (default 100)

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
        return {"ticker": t, "count": 0, "prices": [], "source": None, "cached": False, "error": error}

    # TIME_SERIES_DAILY free-tier endpoint: fields are
    # "1. open", "2. high", "3. low", "4. close", "5. volume"
    av = get_daily_prices(t)
    if av["success"]:
        ts: dict = av["data"].get("Time Series (Daily)", {})
        prices = []
        for date in sorted(ts.keys(), reverse=True)[:days]:
            row = ts[date]
            close = round(float(row["4. close"]), 4)
            prices.append({
                "date": date,
                "open": round(float(row["1. open"]), 4),
                "high": round(float(row["2. high"]), 4),
                "low": round(float(row["3. low"]), 4),
                "close": close,
                "adjusted_close": close,   # free tier has no split-adjusted field
                "volume": int(row["5. volume"]),
            })
        return {
            "ticker": t,
            "count": len(prices),
            "prices": prices,
            "source": "cache" if av["cached"] else "alpha_vantage",
            "cached": av["cached"],
            "error": None,
        }

    # Fall back to yfinance for every AV error except a confirmed bad ticker.
    # yfinance period must be a preset string; map days to the nearest valid preset.
    if _should_try_yfinance(av["error"]):
        yf_period = "1y" if days > 90 else ("3mo" if days > 30 else "1mo")
        try:
            hist = yf.Ticker(t).history(period=yf_period)
            if not hist.empty:
                prices = [
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "open": round(float(row["Open"]), 4),
                        "high": round(float(row["High"]), 4),
                        "low": round(float(row["Low"]), 4),
                        "close": round(float(row["Close"]), 4),
                        "adjusted_close": round(float(row["Close"]), 4),
                        "volume": int(row["Volume"]),
                    }
                    for date, row in hist.iloc[::-1].iterrows()[:days]  # newest first, capped
                ]
                return {
                    "ticker": t,
                    "count": len(prices),
                    "prices": prices,
                    "source": "yfinance",
                    "cached": False,
                    "error": None,
                }
        except Exception as exc:
            return _empty(str(exc))

    return _empty(av.get("message") or av.get("error"))
