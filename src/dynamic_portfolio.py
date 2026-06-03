"""
src/dynamic_portfolio.py

Dynamic portfolio risk analysis for the /analyze-portfolio endpoint.

Data source priority per ticker
--------------------------------
1. data/processed/returns.csv   — pre-built returns from the static MVP pipeline;
                                   covers all 10 demo tickers back to 2018-01-01.
2. data/cache/prices/<T>.csv    — per-ticker price CSV written by a previous run.
3. Alpha Vantage provider        — cache-first; free tier returns ~100 days.
4. yfinance                      — final fallback; result is cached for future runs.

All calculations are backward-looking.
This module never returns buy/sell recommendations or investment advice.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from metrics import (
    annualized_return,
    annualized_volatility,
    sharpe_ratio,
    max_drawdown,
    value_at_risk,
    conditional_var,
)

# ── paths & constants ──────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
_PROCESSED_RETURNS = _PROJECT_ROOT / "data" / "processed" / "returns.csv"
_PROCESSED_PRICES  = _PROJECT_ROOT / "data" / "processed" / "prices.csv"
_PRICE_CACHE_DIR   = _PROJECT_ROOT / "data" / "cache" / "prices"

TRADING_DAYS = 252
FETCH_START  = "2018-01-01"

# Synthetic cash asset — zero daily returns, reduces portfolio volatility
CASH_TICKER = "CASH"

_ETF_BLOCKLIST: frozenset[str] = frozenset(
    {"SPY", "QQQ", "TLT", "IEF", "AGG", "GLD", "SLV", "VTI", "VOO", "XLK", "XLF"}
)

STRESS_PERIODS: list[dict[str, str]] = [
    {"name": "COVID Crash",            "start": "2020-02-19", "end": "2020-03-23"},
    {"name": "2022 Rate-Hike Selloff", "start": "2022-01-03", "end": "2022-10-14"},
]


# ── Priority-1: processed returns file ────────────────────────────────────────

def _load_from_processed_returns(
    tickers: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """
    Read data/processed/returns.csv and return (returns_df, found_tickers).

    Only loads the columns that match the requested tickers.
    Returns an empty DataFrame + empty list when the file is absent or has no
    matching columns.
    """
    if not _PROCESSED_RETURNS.exists():
        return pd.DataFrame(), []

    try:
        df = pd.read_csv(_PROCESSED_RETURNS, index_col=0, parse_dates=True)
    except Exception:
        return pd.DataFrame(), []

    found = [t for t in tickers if t in df.columns]
    if not found:
        return pd.DataFrame(), []

    result = df[found].dropna()
    print(f"[DataSource] using processed returns file — tickers: {found} ({len(result)} rows)")
    return result, found


# ── Priority-2: per-ticker CSV cache ──────────────────────────────────────────

def _load_from_price_cache(ticker: str) -> pd.Series | None:
    """
    Load a ticker's price CSV written by a previous download (any age).
    Returns a sorted DatetimeIndex Series or None.
    """
    path = _PRICE_CACHE_DIR / f"{ticker}.csv"
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        s = df.squeeze()
        if isinstance(s, pd.DataFrame):        # shouldn't happen, be safe
            s = s.iloc[:, 0]
        s = s.dropna().sort_index()
        s.name = ticker
        print(f"[DataSource] {ticker}: using cached price data ({len(s)} days)")
        return s
    except Exception:
        return None


# ── Priority-3: Alpha Vantage ─────────────────────────────────────────────────

def _load_from_alpha_vantage(ticker: str) -> pd.Series | None:
    """
    Fetch prices from Alpha Vantage (honours its own JSON cache).
    Free tier returns ~100 recent trading days.
    Returns None on any error.
    """
    try:
        from providers.alpha_vantage_provider import get_daily_prices

        av = get_daily_prices(ticker)
        if not av.get("success"):
            return None

        ts: dict = av["data"].get("Time Series (Daily)", {})
        if not ts:
            return None

        s = pd.Series(
            {date: float(row["4. close"]) for date, row in ts.items()},
            dtype=float,
        )
        s.index = pd.to_datetime(s.index)
        s = s.sort_index().dropna()
        s.name = ticker

        label = "cached Alpha Vantage" if av.get("cached") else "Alpha Vantage"
        print(f"[DataSource] {ticker}: using {label} ({len(s)} days)")
        return s
    except Exception:
        return None


# ── Priority-4: yfinance fallback ─────────────────────────────────────────────

def _load_from_yfinance(ticker: str) -> pd.Series | None:
    """
    Download adjusted close prices from yfinance back to FETCH_START.
    On success the result is written to _PRICE_CACHE_DIR for future use.
    Returns None on failure.
    """
    _PRICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        raw = yf.download(
            ticker,
            start=FETCH_START,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if raw.empty:
            return None

        # Flatten MultiIndex columns (yfinance ≥ 0.2 sometimes emits them)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        close = raw["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        close = close.dropna().sort_index()
        close.name = ticker
        close.index = pd.to_datetime(close.index)

        # Cache for future requests
        cache_path = _PRICE_CACHE_DIR / f"{ticker}.csv"
        close.to_frame().to_csv(cache_path)

        print(f"[DataSource] {ticker}: using yfinance fallback ({len(close)} days)")
        return close
    except Exception as exc:
        print(f"[DataSource] {ticker}: yfinance failed — {exc}")
        return None


# ── Latest-price helper (used by shares mode in the API layer) ────────────────

def get_latest_price(ticker: str) -> float | None:
    """
    Return the most recent closing price for *ticker* from any available source.
    Tries the price cache, then Alpha Vantage, then yfinance.
    Returns None if all sources fail or the ticker is CASH.
    """
    if ticker == CASH_TICKER:
        return None

    # Try price cache
    prices = _load_from_price_cache(ticker)
    if prices is not None and not prices.empty:
        return float(prices.iloc[-1])

    # Try Alpha Vantage
    prices = _load_from_alpha_vantage(ticker)
    if prices is not None and not prices.empty:
        return float(prices.iloc[-1])

    # Try yfinance
    prices = _load_from_yfinance(ticker)
    if prices is not None and not prices.empty:
        return float(prices.iloc[-1])

    return None


# ── Combined loader for a single ticker not in the processed file ─────────────

def _load_ticker_returns(ticker: str) -> tuple[pd.Series | None, str]:
    """
    Try to obtain daily returns for *ticker* using priority order 2→3→4.

    Returns (returns_series, source_label) or (None, "failed").
    """
    # Priority 2
    prices = _load_from_price_cache(ticker)
    if prices is not None and not prices.empty:
        return prices.pct_change().dropna().rename(ticker), "price_cache"

    # Priority 3
    prices = _load_from_alpha_vantage(ticker)
    if prices is not None and not prices.empty:
        return prices.pct_change().dropna().rename(ticker), "alpha_vantage"

    # Priority 4
    prices = _load_from_yfinance(ticker)
    if prices is not None and not prices.empty:
        return prices.pct_change().dropna().rename(ticker), "yfinance"

    print(f"[DataSource] {ticker}: all sources failed — excluding from analysis")
    return None, "failed"


# ── Public: fetch aligned returns for the whole portfolio ─────────────────────

def fetch_portfolio_returns(
    weights: dict[str, float],
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """
    Return aligned asset daily returns and a weighted portfolio return series.

    Steps
    -----
    1. Load all tickers present in data/processed/returns.csv at once.
    2. For tickers not found there, go through the priority 2→3→4 chain.
    3. Align all series on their common date intersection.
    4. Renormalize weights if any ticker failed entirely.
    5. CASH (if present in weights) is handled as a synthetic zero-return asset.

    Returns
    -------
    (asset_returns_df, portfolio_returns_series, failed_tickers_list)

    Raises ValueError when no ticker yields usable data.
    """
    # Separate CASH from real tickers — CASH has no price history to fetch
    has_cash = CASH_TICKER in weights
    tickers = [t for t in weights if t != CASH_TICKER]

    # ── Priority 1: processed file ──────────────────────────────────────────
    processed_df, found_in_processed = _load_from_processed_returns(tickers)
    remaining = [t for t in tickers if t not in found_in_processed]

    # ── Priority 2-4: individual ticker fetch ───────────────────────────────
    extra_returns: dict[str, pd.Series] = {}
    failed: list[str] = []

    for ticker in remaining:
        series, _source = _load_ticker_returns(ticker)
        if series is None:
            failed.append(ticker)
        else:
            extra_returns[ticker] = series

    # ── Merge all return series into a single DataFrame ─────────────────────
    if processed_df.empty and not extra_returns:
        raise ValueError(
            "Could not fetch price data for any of the requested tickers. "
            "Ensure data/processed/returns.csv exists (run: python src/data_loader.py "
            "and python src/portfolio.py) or check your internet connection."
        )

    if processed_df.empty:
        returns_df = pd.DataFrame(extra_returns).dropna()
    elif not extra_returns:
        returns_df = processed_df
    else:
        # Inner join: only keep dates common to both sources
        extra_df = pd.DataFrame(extra_returns)
        returns_df = processed_df.join(extra_df, how="inner").dropna()

    if returns_df.empty:
        raise ValueError(
            "After aligning all price series on common dates the dataset is empty. "
            "This can happen when a newly-fetched ticker has no overlapping dates "
            "with the processed returns file."
        )

    # ── Add CASH as a zero-return column (dampens portfolio volatility) ─────
    if has_cash:
        returns_df[CASH_TICKER] = 0.0

    # ── Build weighted portfolio return ─────────────────────────────────────
    available = {t: weights[t] for t in weights if t in returns_df.columns}
    w_sum = sum(available.values())
    norm_w = {t: w / w_sum for t, w in available.items()}
    weight_series = pd.Series(norm_w)

    port_returns = returns_df[weight_series.index].dot(weight_series)
    port_returns.name = "portfolio"

    return returns_df, port_returns, failed


# ── Risk metrics ───────────────────────────────────────────────────────────────

def compute_risk_metrics(port_returns: pd.Series) -> dict[str, Any]:
    return {
        "annualized_return":     round(annualized_return(port_returns),     6),
        "annualized_volatility": round(annualized_volatility(port_returns), 6),
        "sharpe_ratio":          round(sharpe_ratio(port_returns),          4),
        "max_drawdown":          round(max_drawdown(port_returns),          6),
        "var_95":                round(value_at_risk(port_returns, 0.95),   6),
        "cvar_95":               round(conditional_var(port_returns, 0.95), 6),
        "var_99":                round(value_at_risk(port_returns, 0.99),   6),
        "cvar_99":               round(conditional_var(port_returns, 0.99), 6),
        "trading_days_used":     int(len(port_returns)),
        "data_start":            str(port_returns.index[0].date()),
        "data_end":              str(port_returns.index[-1].date()),
    }


# ── Correlation matrix ─────────────────────────────────────────────────────────

def compute_correlation_matrix(
    returns_df: pd.DataFrame,
) -> dict[str, dict[str, float]]:
    corr = returns_df.corr().round(4)
    return {col: corr[col].to_dict() for col in corr.columns}


# ── Top risk contributors ──────────────────────────────────────────────────────

def compute_top_risk_contributors(
    weights: dict[str, float],
    returns_df: pd.DataFrame,
    port_returns: pd.Series,
) -> list[dict[str, Any]]:
    assets = [t for t in weights if t in returns_df.columns]
    if not assets:
        return []

    asset_returns = returns_df[assets]
    w = pd.Series({t: weights[t] for t in assets})
    w = w / w.sum()

    vol         = asset_returns.std() * np.sqrt(TRADING_DAYS)
    wv_contrib  = w * vol
    corr_port   = asset_returns.corrwith(port_returns)
    worst_dates = port_returns.nsmallest(5).index
    worst_avg   = asset_returns.loc[asset_returns.index.isin(worst_dates)].mean()

    table = pd.DataFrame(
        {
            "weight":                                 w,
            "annualized_volatility":                  vol.round(6),
            "weight_volatility_contribution":         wv_contrib.round(6),
            "correlation_with_portfolio":             corr_port.round(4),
            "average_return_on_worst_5_portfolio_days": worst_avg.round(6),
        }
    ).sort_values("weight_volatility_contribution", ascending=False)

    return [
        {
            "ticker":                                  ticker,
            "weight":                                  round(float(row["weight"]), 6),
            "annualized_volatility":                   round(float(row["annualized_volatility"]), 6),
            "weight_volatility_contribution":          round(float(row["weight_volatility_contribution"]), 6),
            "correlation_with_portfolio":              round(float(row["correlation_with_portfolio"]), 4),
            "average_return_on_worst_5_portfolio_days": round(
                float(row["average_return_on_worst_5_portfolio_days"]), 6
            ),
        }
        for ticker, row in table.iterrows()
    ]


# ── Stress analysis ────────────────────────────────────────────────────────────

def compute_stress_analysis(
    weights: dict[str, float],
    returns_df: pd.DataFrame,
    port_returns: pd.Series,
) -> list[dict[str, Any]]:
    assets = [t for t in weights if t in returns_df.columns]
    w = pd.Series({t: weights[t] for t in assets})
    w = w / w.sum()

    results: list[dict[str, Any]] = []

    for period in STRESS_PERIODS:
        name, start, end = period["name"], period["start"], period["end"]
        port_slice  = port_returns.loc[start:end]
        asset_slice = returns_df[assets].loc[start:end]

        if port_slice.empty:
            results.append(
                {
                    "period": name, "start": start, "end": end,
                    "portfolio_cumulative_return": None,
                    "portfolio_max_drawdown": None,
                    "worst_contributors": [],
                    "note": "No trading data available for this stress window.",
                }
            )
            continue

        cum_return = float((1 + port_slice).prod() - 1)
        cum        = (1 + port_slice).cumprod()
        mdd        = float(((cum - cum.cummax()) / cum.cummax()).min())

        asset_cum        = (1 + asset_slice).prod() - 1
        weighted_contrib = (w * asset_cum).dropna().sort_values()

        worst = [
            {
                "ticker":                  ticker,
                "weight":                  round(float(w.get(ticker, 0)), 6),
                "asset_cumulative_return": round(float(asset_cum.get(ticker, 0)), 6),
                "weighted_contribution":   round(float(val), 6),
            }
            for ticker, val in weighted_contrib.head(3).items()
        ]

        results.append(
            {
                "period":                       name,
                "start":                        start,
                "end":                          end,
                "portfolio_cumulative_return":  round(cum_return, 6),
                "portfolio_max_drawdown":       round(mdd, 6),
                "worst_contributors":           worst,
            }
        )

    return results


# ── Qdrant company risk evidence ───────────────────────────────────────────────

def compute_company_risk_evidence(
    weights: dict[str, float],
    query: str = "key business risks revenue concentration regulatory",
    top_k: int = 3,
) -> dict[str, Any]:
    """
    Query Qdrant for risk factor evidence for the top non-ETF holdings by weight.
    Up to 5 tickers are queried. ETFs are silently skipped.
    Never raises — returns {} on any import or connectivity failure.
    """
    try:
        import qdrant_ingestion
    except ImportError:
        return {}

    candidates = sorted(
        [(t, w) for t, w in weights.items()
         if t not in _ETF_BLOCKLIST and t != CASH_TICKER],
        key=lambda x: x[1],
        reverse=True,
    )[:5]

    def _query_one(ticker: str) -> tuple[str, Any]:
        try:
            hits = qdrant_ingestion.retrieve_company_risks(
                query=query, tickers=[ticker], top_k=top_k
            )
            return ticker, hits if hits else {
                "message": (
                    f"No company risk evidence available yet for {ticker}. "
                    "Run SEC extraction and Qdrant ingestion for this ticker first."
                )
            }
        except Exception as exc:
            return ticker, {"message": f"Qdrant query failed for {ticker}: {exc}"}

    if not candidates:
        return {}

    evidence: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=len(candidates)) as pool:
        for ticker, result in pool.map(lambda t: _query_one(t[0]), candidates):
            evidence[ticker] = result

    return evidence


# ── Main entry point ───────────────────────────────────────────────────────────

def analyze_portfolio(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Run the full dynamic risk analysis pipeline.

    Parameters
    ----------
    holdings : list of {"ticker": str, "weight": float}
               Weights must already be normalized so they sum to ≈ 1.0.
    """
    weights = {h["ticker"]: h["weight"] for h in holdings}

    returns_df, port_returns, failed = fetch_portfolio_returns(weights)

    warnings: list[str] = []
    if failed:
        warnings.append(
            f"Price data could not be fetched for: {', '.join(failed)}. "
            "These tickers were excluded from all calculations and the remaining "
            "weights were renormalized."
        )

    return {
        "risk_metrics":           compute_risk_metrics(port_returns),
        "correlation_matrix":     compute_correlation_matrix(returns_df),
        "top_risk_contributors":  compute_top_risk_contributors(weights, returns_df, port_returns),
        "stress_analysis":        compute_stress_analysis(weights, returns_df, port_returns),
        "company_risk_evidence":  compute_company_risk_evidence(weights),
        "failed_tickers":         failed,
        "warnings":               warnings,
        # Internal — not JSON-serializable; extracted and popped by the API layer
        "_returns_df":            returns_df,
        "_port_returns":          port_returns,
    }
