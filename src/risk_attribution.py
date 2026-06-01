"""
src/risk_attribution.py

Risk attribution and risk driver analysis.

Six heuristic dimensions:
  1. Market Risk        — portfolio beta relative to SPY
  2. Sector Risk        — sector concentration from holding profiles
  3. Style/Factor Risk  — high-beta / high-vol / growth classification
  4. Macro Risk         — sensitivity to QQQ and TLT benchmarks
  5. Concentration Risk — HHI, top-N position weights
  6. Tail Risk          — VaR / CVaR / max-drawdown interpretation

One statistical model:
  7. Proxy Factor Exposure Regression — OLS of portfolio daily returns on
     market proxy ETF returns (SPY, QQQ, TLT).
     Returns beta, t-stat, p-value, R², adj-R².
     This is proxy-based regression, not formal academic factor modeling.

Each function returns:
  {
      "risk_level":    "Low" | "Moderate" | "High" | "Unknown",
      "available":     bool,
      "metrics":       { ... },
      "summary":       str,       — full paragraph
      "short_reason":  str,       — one-liner for the driver ranking table
      "drivers":       [str, ...]
  }

compute_risk_attribution() is the single entry point called by the API layer.
Never raises — all errors are caught and returned as risk_level="Unknown".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

TRADING_DAYS = 252
_PROCESSED_RETURNS = Path(__file__).parent.parent / "data" / "processed" / "returns.csv"


def _pct(v: float, d: int = 1) -> str:
    return f"{v * 100:.{d}f}%"


def _load_benchmark(ticker: str, returns_df: pd.DataFrame) -> pd.Series | None:
    """Return a benchmark return series from returns_df or the processed file."""
    if ticker in returns_df.columns:
        return returns_df[ticker]
    if _PROCESSED_RETURNS.exists():
        try:
            df = pd.read_csv(_PROCESSED_RETURNS, index_col=0, parse_dates=True)
            if ticker in df.columns:
                return df[ticker]
        except Exception:
            pass
    return None


# ── 1. Market Risk ─────────────────────────────────────────────────────────────

def calculate_market_risk_attribution(
    weights: dict[str, float],
    returns_df: pd.DataFrame,
    port_returns: pd.Series,
) -> dict[str, Any]:
    """Compute portfolio beta and correlation relative to SPY."""
    try:
        spy = _load_benchmark("SPY", returns_df)
        if spy is None or spy.empty or port_returns.empty:
            return {
                "risk_level": "Unknown", "available": False, "metrics": {},
                "summary": "Market sensitivity could not be computed — SPY benchmark data not available.",
                "short_reason": "SPY data unavailable",
                "drivers": [],
            }

        common = port_returns.index.intersection(spy.index)
        if len(common) < 30:
            return {
                "risk_level": "Unknown", "available": False, "metrics": {},
                "summary": "Insufficient data overlap with SPY to estimate portfolio beta.",
                "short_reason": "Insufficient data",
                "drivers": [],
            }

        p = port_returns.loc[common].values
        s = spy.loc[common].values
        cov = np.cov(p, s)
        beta = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] > 0 else 0.0
        corr = float(port_returns.loc[common].corr(spy.loc[common]))
        r2 = round(corr ** 2, 4)
        beta = round(beta, 3)
        corr = round(corr, 3)

        if beta > 1.3:
            risk_level = "High"
            summary = (
                f"This portfolio has elevated market sensitivity with a beta of {beta:.2f} "
                f"relative to SPY. Returns tend to amplify broad equity market moves in both "
                f"directions — a 10% market decline would imply roughly a {beta * 10:.0f}% loss "
                f"for this portfolio based on historical behavior."
            )
        elif beta > 0.85:
            risk_level = "Moderate"
            summary = (
                f"This portfolio has moderate market sensitivity (beta {beta:.2f} vs SPY). "
                f"Returns closely track broad equity market movements, with {_pct(r2)} of "
                f"portfolio variance explained by market moves."
            )
        elif beta >= 0:
            risk_level = "Low"
            summary = (
                f"This portfolio has relatively low market sensitivity (beta {beta:.2f} vs SPY). "
                f"It tends to move less than the broad equity market."
            )
        else:
            risk_level = "Low"
            summary = (
                f"This portfolio has a negative or near-zero beta ({beta:.2f}) relative to SPY, "
                f"suggesting limited or inverse correlation with broad equity markets."
            )

        drivers = [f"Estimated portfolio beta vs SPY: {beta:.2f}."]
        if corr > 0.85:
            drivers.append(
                f"High SPY correlation ({corr:.2f}) — portfolio returns are closely tied to "
                f"broad equity market movements."
            )
        if r2 > 0.7:
            drivers.append(
                f"R² of {r2:.2f}: {r2 * 100:.0f}% of portfolio variance is explained by broad market moves."
            )

        return {
            "risk_level":   risk_level,
            "available":    True,
            "metrics":      {"portfolio_beta": beta, "spy_correlation": corr, "r_squared": r2, "data_days": int(len(common))},
            "summary":      summary,
            "short_reason": f"Beta {beta:.2f} vs SPY",
            "drivers":      drivers,
        }
    except Exception as exc:
        return {
            "risk_level": "Unknown", "available": False, "metrics": {},
            "summary": f"Market risk analysis unavailable: {str(exc)[:120]}",
            "short_reason": "Calculation error",
            "drivers": [],
        }


# ── 2. Sector Risk ─────────────────────────────────────────────────────────────

def calculate_sector_concentration(
    enriched_holdings: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Aggregate portfolio weights by sector.
    ETF holdings are separated and excluded from equity sector concentration.
    """
    try:
        equity_sectors: dict[str, float] = {}
        etf_weight = 0.0
        unknown_weight = 0.0
        etf_tickers: list[str] = []

        for h in enriched_holdings:
            weight = float(h.get("weight") or 0)
            ticker = h.get("ticker", "")
            profile = h.get("profile") or {}
            sector = (profile.get("sector") or "").strip()
            sec_type = (profile.get("security_type") or "").strip()

            if sec_type == "ETF" or sector == "ETF":
                etf_weight += weight
                etf_tickers.append(ticker)
                continue

            if not sector or sector.lower() in ("unknown", "none", "n/a", "—", "-", ""):
                unknown_weight += weight
                continue

            equity_sectors[sector] = equity_sectors.get(sector, 0) + weight

        total_classified = sum(equity_sectors.values())
        all_sector_weights: dict[str, float] = {}
        all_sector_weights.update(equity_sectors)
        if etf_weight > 0:
            all_sector_weights["ETF"] = etf_weight
        if unknown_weight > 0:
            all_sector_weights["Unknown"] = unknown_weight

        if not equity_sectors and not etf_weight:
            return {
                "risk_level": "Unknown", "available": False,
                "metrics": {"sector_weights": all_sector_weights, "num_sectors": 0},
                "summary": (
                    "Sector information is unavailable for these holdings. "
                    "Ensure company profiles are loaded for sector analysis."
                ),
                "short_reason": "No sector data",
                "drivers": [],
            }

        sorted_equity = sorted(equity_sectors.items(), key=lambda x: x[1], reverse=True)
        sorted_all = sorted(all_sector_weights.items(), key=lambda x: x[1], reverse=True)

        num_sectors = len(equity_sectors)
        top3_equity_weight = sum(v for _, v in sorted_equity[:3])

        if sorted_equity:
            top_sector, top_weight = sorted_equity[0]
        else:
            # No equity holdings — sector concentration is not assessable
            top_sector, top_weight = "ETF", etf_weight

        # Risk level based on equity sector concentration only
        # ETF-only or no-equity portfolios: sector concentration is not applicable
        if not equity_sectors:
            risk_level = "Low"
        elif top_weight > 0.60:
            risk_level = "High"
        elif top_weight > 0.35:
            risk_level = "Moderate"
        else:
            risk_level = "Low"

        # Build summary
        parts: list[str] = []
        if top_weight > 0.50 and equity_sectors:
            parts.append(
                f"{top_sector} represents {_pct(top_weight)} of the portfolio, "
                f"creating significant sector concentration risk."
            )
        elif top_weight > 0.30 and equity_sectors:
            parts.append(
                f"Moderate sector concentration: {top_sector} at {_pct(top_weight)}."
            )
        elif equity_sectors:
            parts.append(
                f"The portfolio appears reasonably diversified across {num_sectors} equity sectors, "
                f"with {top_sector} as the largest at {_pct(top_weight)}."
            )

        if unknown_weight > 0.15:
            parts.append(
                f"However, {_pct(unknown_weight)} of holdings are missing sector classification, "
                f"so the sector risk estimate should be interpreted with caution."
            )
        if etf_weight > 0:
            etf_label = ", ".join(etf_tickers[:3])
            parts.append(
                f"ETF holdings ({etf_label}) representing {_pct(etf_weight)} are excluded "
                f"from equity sector concentration analysis."
            )

        summary = " ".join(parts) if parts else "Sector analysis complete."

        drivers: list[str] = []
        if top_weight > 0.35 and equity_sectors:
            drivers.append(f"{top_sector} accounts for {_pct(top_weight)} of portfolio weight.")
        if num_sectors <= 2 and equity_sectors:
            drivers.append("Portfolio equity holdings span only 1–2 sectors, limiting sector diversification.")
        if num_sectors >= 5:
            drivers.append(f"Equity exposure spread across {num_sectors} sectors provides diversification.")
        if unknown_weight > 0.2:
            drivers.append(f"{_pct(unknown_weight)} of holdings have no sector classification (shown as Unknown).")

        short = f"{top_sector} {_pct(top_weight)}" if equity_sectors else f"ETF {_pct(etf_weight)}"

        return {
            "risk_level":   risk_level,
            "available":    True,
            "metrics": {
                "sector_weights":        {k: round(v, 4) for k, v in sorted_all},
                "equity_sector_weights": {k: round(v, 4) for k, v in sorted_equity},
                "top_sector":            top_sector,
                "top_sector_weight":     round(top_weight, 4),
                "num_equity_sectors":    num_sectors,
                "etf_weight":            round(etf_weight, 4),
                "etf_tickers":           etf_tickers,
                "unknown_weight":        round(unknown_weight, 4),
                "top_3_equity_weight":   round(top3_equity_weight, 4),
            },
            "summary":      summary,
            "short_reason": short,
            "drivers":      drivers,
        }
    except Exception as exc:
        return {
            "risk_level": "Unknown", "available": False, "metrics": {},
            "summary": f"Sector analysis unavailable: {str(exc)[:120]}",
            "short_reason": "Calculation error",
            "drivers": [],
        }


# ── 3. Style / Factor Risk ─────────────────────────────────────────────────────

_GROWTH_SECTORS = {"Technology", "Communication Services", "Consumer Cyclical"}


def calculate_style_factor_exposure(
    weights: dict[str, float],
    top_risk_contributors: list[dict[str, Any]],
    enriched_holdings: list[dict[str, Any]],
    market_risk: dict[str, Any],
) -> dict[str, Any]:
    """
    Classify portfolio style: high-beta, high-vol, growth/tech, or defensive.

    TODO: Extend with additional proxy factors when data becomes available.
    The current classification is a simplified rule-based proxy.
    """
    try:
        if not top_risk_contributors:
            return {
                "risk_level": "Unknown", "available": False, "metrics": {},
                "summary": "Style factor analysis requires risk contributor data.",
                "short_reason": "No contributor data",
                "drivers": [],
            }

        total_weight = sum(weights.values()) or 1.0
        avg_vol = 0.0
        high_vol_tickers: list[str] = []

        for c in top_risk_contributors:
            ticker = c.get("ticker", "")
            w = weights.get(ticker, 0) / total_weight
            vol = float(c.get("annualized_volatility") or 0)
            avg_vol += w * vol
            if vol > 0.35:
                high_vol_tickers.append(ticker)

        beta = (market_risk.get("metrics") or {}).get("portfolio_beta")

        growth_weight = 0.0
        for h in enriched_holdings:
            sector = ((h.get("profile") or {}).get("sector") or "").strip()
            w = float(h.get("weight") or 0)
            if sector in _GROWTH_SECTORS:
                growth_weight += w

        styles: list[str] = []
        if beta is not None and beta > 1.25:
            styles.append("high-beta")
        if avg_vol > 0.28:
            styles.append("high-volatility")
        if growth_weight > 0.5:
            styles.append("growth/tech-heavy")

        if not styles:
            if beta is not None and beta < 0.7:
                styles.append("defensive/low-beta")
            elif avg_vol < 0.18:
                styles.append("low-volatility")
            else:
                styles.append("balanced")

        high_risk = {"high-beta", "high-volatility"}
        if sum(1 for s in styles if s in high_risk) >= 2:
            risk_level = "High"
        elif any(s in {"high-beta", "high-volatility", "growth/tech-heavy"} for s in styles):
            risk_level = "Moderate"
        else:
            risk_level = "Low"

        style_str = ", ".join(styles)
        summary = f"The portfolio exhibits a {style_str} style profile."
        if avg_vol > 0:
            summary += (
                f" Weighted average annualized volatility across holdings is {_pct(avg_vol)}, "
                f"which is {'above' if avg_vol > 0.25 else 'within'} typical equity ranges."
            )
        if beta is not None:
            direction = "above" if beta > 1 else "below"
            summary += (
                f" Portfolio beta of {beta:.2f} indicates {direction}-market return amplification. "
                f"This style profile makes the portfolio sensitive to growth-stock and technology sector drawdowns."
            )

        drivers = [f"Dominant style classification: {style_str}."]
        if high_vol_tickers:
            drivers.append(f"High-volatility positions (>35% ann. vol): {', '.join(high_vol_tickers[:4])}.")
        if growth_weight > 0.3:
            drivers.append(f"Growth/tech sector exposure: {_pct(growth_weight)} of portfolio.")

        return {
            "risk_level":   risk_level,
            "available":    True,
            "metrics": {
                "style_tags":             styles,
                "weighted_avg_volatility": round(avg_vol, 4),
                "portfolio_beta":          beta,
                "growth_tech_weight":      round(growth_weight, 4),
                "high_vol_tickers":        high_vol_tickers[:5],
            },
            "summary":      summary,
            "short_reason": f"{style_str}, avg vol {_pct(avg_vol)}",
            "drivers":      drivers,
        }
    except Exception as exc:
        return {
            "risk_level": "Unknown", "available": False, "metrics": {},
            "summary": f"Style factor analysis unavailable: {str(exc)[:120]}",
            "short_reason": "Calculation error",
            "drivers": [],
        }


# ── 4. Macro Risk ──────────────────────────────────────────────────────────────

def calculate_macro_risk_exposure(
    weights: dict[str, float],
    returns_df: pd.DataFrame,
    port_returns: pd.Series,
) -> dict[str, Any]:
    """
    Estimate portfolio sensitivity to macro benchmarks.
    - QQQ: tech/growth factor proxy
    - TLT: long-duration rate-sensitivity proxy

    Correlation thresholds are applied conservatively — weak correlations
    are explicitly noted as inconclusive rather than over-interpreted.

    TODO: VIX proxy (volatility-shock sensitivity) is planned as a future
    extension — requires reliable ^VIX daily data in the pipeline.
    10Y Treasury yield data is not currently available; TLT is used as a
    duration/rates proxy only and does not represent direct yield sensitivity.
    """
    try:
        if port_returns.empty:
            return {
                "risk_level": "Unknown", "available": False, "metrics": {},
                "summary": "Macro sensitivity analysis requires portfolio return data.",
                "short_reason": "No return data",
                "drivers": [],
            }

        benchmarks = {"QQQ": "tech/growth", "TLT": "rate/duration"}
        correlations: dict[str, float] = {}
        betas: dict[str, float] = {}

        for ticker in benchmarks:
            bench = _load_benchmark(ticker, returns_df)
            if bench is None or bench.empty:
                continue
            common = port_returns.index.intersection(bench.index)
            if len(common) < 30:
                continue
            p = port_returns.loc[common]
            b = bench.loc[common]
            corr = float(p.corr(b))
            cov = np.cov(p.values, b.values)
            beta = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] > 0 else 0.0
            correlations[ticker] = round(corr, 3)
            betas[ticker] = round(beta, 3)

        if not correlations:
            return {
                "risk_level": "Unknown", "available": False, "metrics": {},
                "summary": "Macro benchmark data (QQQ, TLT) not available in this dataset.",
                "short_reason": "No benchmark data",
                "drivers": [],
            }

        qqq_corr = correlations.get("QQQ", 0.0)
        tlt_corr = correlations.get("TLT", 0.0)

        vulnerabilities: list[str] = []
        if qqq_corr > 0.80:
            vulnerabilities.append("tech_growth_sensitive")
        if tlt_corr > 0.50:
            vulnerabilities.append("rate_sensitive_positive")
        elif tlt_corr < -0.40:
            vulnerabilities.append("rate_sensitive_inverse")
        # Intentionally conservative: weak correlations (|r| < 0.4 for TLT)
        # are not flagged to avoid over-interpreting proxy noise

        risk_level = "High" if len(vulnerabilities) >= 2 else "Moderate" if vulnerabilities else "Low"

        parts: list[str] = []

        if "QQQ" in correlations:
            if qqq_corr > 0.80:
                parts.append(
                    f"The portfolio shows strong growth/technology sensitivity "
                    f"(QQQ correlation: {qqq_corr:.2f}). Tech sector drawdowns or "
                    f"growth-stock valuation compression may disproportionately affect performance."
                )
            elif qqq_corr > 0.60:
                parts.append(
                    f"The portfolio shows moderate tech/growth sensitivity "
                    f"(QQQ correlation: {qqq_corr:.2f})."
                )
            else:
                parts.append(
                    f"The portfolio shows limited direct tech/growth sensitivity "
                    f"(QQQ correlation: {qqq_corr:.2f})."
                )

        if "TLT" in correlations:
            if abs(tlt_corr) < 0.25:
                parts.append(
                    f"Rate sensitivity is not clearly detected in the current proxy analysis "
                    f"(TLT correlation: {tlt_corr:.2f}). Macro risk is mainly interpreted through "
                    f"growth-stock and volatility exposure rather than direct duration sensitivity."
                )
            elif tlt_corr > 0.50:
                parts.append(
                    f"Positive rate sensitivity detected (TLT correlation: {tlt_corr:.2f}), "
                    f"suggesting exposure to long-duration asset dynamics."
                )
            elif tlt_corr < -0.40:
                parts.append(
                    f"The portfolio shows inverse rate sensitivity (TLT correlation: {tlt_corr:.2f}), "
                    f"meaning it may be vulnerable to rising interest rates."
                )
            else:
                parts.append(
                    f"Weak rate sensitivity (TLT correlation: {tlt_corr:.2f}) — "
                    f"inconclusive with current proxy data."
                )

        summary = " ".join(parts) if parts else "Macro sensitivity analysis complete."

        drivers: list[str] = []
        for ticker, corr in correlations.items():
            label = benchmarks.get(ticker, ticker)
            drivers.append(f"{ticker} ({label}) correlation: {corr:.2f}.")
        if "tech_growth_sensitive" in vulnerabilities:
            drivers.append("High QQQ correlation — portfolio is sensitive to tech-sector drawdowns.")

        short = f"QQQ {qqq_corr:.2f}, TLT {tlt_corr:.2f}" if "TLT" in correlations else f"QQQ {qqq_corr:.2f}"

        return {
            "risk_level":   risk_level,
            "available":    True,
            "metrics": {
                "benchmark_correlations": correlations,
                "benchmark_betas":        betas,
                "vulnerabilities":        vulnerabilities,
            },
            "summary":      summary,
            "short_reason": short,
            "drivers":      drivers,
        }
    except Exception as exc:
        return {
            "risk_level": "Unknown", "available": False, "metrics": {},
            "summary": f"Macro risk analysis unavailable: {str(exc)[:120]}",
            "short_reason": "Calculation error",
            "drivers": [],
        }


# ── 5. Concentration Risk ──────────────────────────────────────────────────────

def calculate_concentration_risk(
    weights: dict[str, float],
    top_risk_contributors: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute HHI and top-N weight concentration diagnostics."""
    try:
        if not weights:
            return {
                "risk_level": "Unknown", "available": False, "metrics": {},
                "summary": "No holdings data to analyze concentration.",
                "short_reason": "No data",
                "drivers": [],
            }

        sorted_h = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        n = len(sorted_h)
        top1_ticker, top1 = sorted_h[0] if n >= 1 else ("", 0.0)
        top3 = sum(w for _, w in sorted_h[:3])
        top5 = sum(w for _, w in sorted_h[:5])
        hhi = sum(w ** 2 for w in weights.values())
        equal_hhi = 1.0 / n if n > 0 else 0.0

        if top3 > 0.70 or top1 > 0.35:
            risk_level = "High"
        elif top3 > 0.50 or top1 > 0.25:
            risk_level = "Moderate"
        else:
            risk_level = "Low"

        if top3 > 0.65:
            summary = (
                f"The top 3 holdings account for {_pct(top3)} of the portfolio, "
                f"creating high concentration risk. Adverse moves in any of these "
                f"positions could have an outsized impact on total portfolio performance."
            )
        elif top3 > 0.5:
            summary = (
                f"Moderate concentration: the top 3 holdings represent {_pct(top3)} "
                f"of total exposure. The largest single position ({top1_ticker}) is {_pct(top1)}."
            )
        else:
            summary = (
                f"The portfolio shows reasonable position sizing — the top 3 holdings "
                f"represent {_pct(top3)}, with the largest single position "
                f"({top1_ticker}) at {_pct(top1)}."
            )

        drivers: list[str] = []
        if top1 > 0.20:
            drivers.append(f"Largest single position ({top1_ticker}): {_pct(top1)} of portfolio.")
        if top3 > 0.5:
            drivers.append(f"Top 3 holdings represent {_pct(top3)} of total exposure.")
        if n <= 5:
            drivers.append(f"Only {n} holdings — limited diversification by position count.")
        if hhi > equal_hhi * 1.2:
            drivers.append(
                f"HHI of {hhi:.3f} is above the equal-weight benchmark of {equal_hhi:.3f}, "
                f"indicating above-average concentration."
            )

        return {
            "risk_level":   risk_level,
            "available":    True,
            "metrics": {
                "num_holdings":    n,
                "top_1_ticker":    top1_ticker,
                "top_1_weight":    round(top1, 4),
                "top_3_weight":    round(top3, 4),
                "top_5_weight":    round(top5, 4),
                "hhi":             round(hhi, 4),
                "equal_weight_hhi": round(equal_hhi, 4),
            },
            "summary":      summary,
            "short_reason": f"Top-3 = {_pct(top3)}, {n} holdings",
            "drivers":      drivers,
        }
    except Exception as exc:
        return {
            "risk_level": "Unknown", "available": False, "metrics": {},
            "summary": f"Concentration analysis unavailable: {str(exc)[:120]}",
            "short_reason": "Calculation error",
            "drivers": [],
        }


# ── 6. Tail Risk ───────────────────────────────────────────────────────────────

def calculate_tail_risk_attribution(
    port_returns: pd.Series,
    risk_metrics: dict[str, Any],
    stress_analysis: list[dict[str, Any]],
    style_risk: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Interpret VaR, CVaR, max drawdown, and historical stress behavior."""
    try:
        var_95  = float(risk_metrics.get("var_95")  or 0)
        cvar_95 = float(risk_metrics.get("cvar_95") or 0)
        var_99  = float(risk_metrics.get("var_99")  or 0)
        mdd     = float(risk_metrics.get("max_drawdown") or 0)

        var_high   = var_95  > 0.04
        var_elev   = var_95  > 0.025
        cvar_high  = cvar_95 > 0.07
        cvar_elev  = cvar_95 > 0.045
        mdd_high   = abs(mdd) > 0.45
        mdd_elev   = abs(mdd) > 0.25

        severe   = sum([var_high,  cvar_high,  mdd_high])
        elevated = sum([var_elev,  cvar_elev,  mdd_elev])

        risk_level = "High" if severe >= 2 else "Moderate" if (elevated >= 2 or severe >= 1) else "Low"

        worst_stress = None
        valid_stress = [s for s in (stress_analysis or []) if s.get("portfolio_cumulative_return") is not None]
        if valid_stress:
            worst_stress = min(valid_stress, key=lambda s: s["portfolio_cumulative_return"])

        # Determine tail driver context from style
        style_tags = (style_risk or {}).get("metrics", {}).get("style_tags", []) if style_risk else []
        growth_beta_driven = any(t in style_tags for t in ("high-beta", "growth/tech-heavy", "high-volatility"))

        parts = [
            f"On a typical adverse day (VaR 95%), the portfolio could lose {_pct(var_95)}.",
            f"In severe tail scenarios (CVaR 95%), the expected loss is {_pct(cvar_95)}.",
            f"The maximum historical drawdown was {_pct(abs(mdd))}.",
        ]
        if worst_stress:
            worst_ret = worst_stress["portfolio_cumulative_return"]
            parts.append(
                f"During the {worst_stress.get('period', 'worst stress period')}, "
                f"the portfolio lost {_pct(abs(worst_ret))} peak-to-trough."
            )
        if growth_beta_driven:
            parts.append(
                "Tail risk appears mainly driven by high-beta technology and growth-stock "
                "exposure — this portfolio has historically experienced amplified drawdowns "
                "during growth-sector selloff regimes."
            )

        summary = " ".join(parts)

        drivers: list[str] = []
        if var_95:
            drivers.append(f"1-day VaR 95%: {_pct(var_95)} — daily loss at 95% confidence.")
        if cvar_95:
            drivers.append(f"Expected Shortfall 95%: {_pct(cvar_95)} — average loss on the worst 5% of trading days.")
        if mdd:
            drivers.append(f"Maximum historical drawdown: {_pct(abs(mdd))}.")
        if var_95 > 0 and cvar_95 > 0:
            ratio = cvar_95 / var_95
            if ratio > 1.5:
                drivers.append(
                    f"CVaR/VaR ratio of {ratio:.2f} suggests a heavy-tailed loss distribution — "
                    f"extreme losses are disproportionately severe."
                )
        if port_returns is not None and not port_returns.empty:
            worst_val = float(port_returns.min())
            worst_date = port_returns.idxmin()
            date_str = str(worst_date.date()) if hasattr(worst_date, "date") else str(worst_date)
            drivers.append(f"Worst single trading day: {_pct(worst_val)} on {date_str}.")

        return {
            "risk_level":   risk_level,
            "available":    True,
            "metrics": {
                "var_95":         round(var_95,       4),
                "cvar_95":        round(cvar_95,      4),
                "var_99":         round(var_99,        4),
                "max_drawdown":   round(abs(mdd),      4),
                "cvar_var_ratio": round(cvar_95 / var_95, 3) if var_95 > 0 else None,
            },
            "summary":      summary,
            "short_reason": f"VaR {_pct(var_95)}, MDD {_pct(abs(mdd))}",
            "drivers":      drivers,
        }
    except Exception as exc:
        return {
            "risk_level": "Unknown", "available": False, "metrics": {},
            "summary": f"Tail risk analysis unavailable: {str(exc)[:120]}",
            "short_reason": "Calculation error",
            "drivers": [],
        }


# ── Overall summary ────────────────────────────────────────────────────────────

def generate_risk_driver_summary(
    market: dict[str, Any],
    sector: dict[str, Any],
    style: dict[str, Any],
    macro: dict[str, Any],
    concentration: dict[str, Any],
    tail: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate all six attribution results into an overall risk profile."""
    all_results: dict[str, dict] = {
        "market_risk":        market,
        "sector_risk":        sector,
        "style_risk":         style,
        "macro_risk":         macro,
        "concentration_risk": concentration,
        "tail_risk":          tail,
    }
    level_scores = {"High": 2, "Moderate": 1, "Low": 0, "Unknown": 0}
    total_score = sum(level_scores.get(r.get("risk_level", "Unknown"), 0) for r in all_results.values())
    available   = sum(1 for r in all_results.values() if r.get("available", False))

    overall_level = "High" if total_score >= 6 else "Moderate" if total_score >= 3 else "Low"

    dominant  = [k for k, r in all_results.items() if r.get("risk_level") == "High"]
    secondary = [k for k, r in all_results.items() if r.get("risk_level") == "Moderate"]

    labels = {
        "market_risk":        "market sensitivity",
        "sector_risk":        "sector concentration",
        "style_risk":         "style/factor exposure",
        "macro_risk":         "macro sensitivity",
        "concentration_risk": "position concentration",
        "tail_risk":          "tail risk",
    }

    dom_readable = [labels.get(d, d) for d in dominant]
    sec_readable = [labels.get(d, d) for d in secondary]

    # Build a contextual summary
    beta  = (market.get("metrics") or {}).get("portfolio_beta")
    top3w = (concentration.get("metrics") or {}).get("top_3_weight")
    top_s = (sector.get("metrics") or {}).get("top_sector")
    top_sw = (sector.get("metrics") or {}).get("top_sector_weight")
    mdd   = (tail.get("metrics") or {}).get("max_drawdown")
    style_tags = (style.get("metrics") or {}).get("style_tags", [])

    summary_parts: list[str] = []

    if dominant:
        summary_parts.append(
            f"Overall portfolio risk is {overall_level}, primarily driven by {', '.join(dom_readable)}."
        )
        # Add key metrics for dominant drivers
        if "concentration_risk" in dominant and top3w is not None:
            summary_parts.append(
                f"The top 3 positions account for {_pct(top3w)} of total weight."
            )
        if "market_risk" in dominant and beta is not None:
            summary_parts.append(
                f"Portfolio beta of {beta:.2f} amplifies broad equity market moves."
            )
        if "style_risk" in dominant and style_tags:
            summary_parts.append(
                f"Style profile ({', '.join(style_tags)}) increases sensitivity to growth/tech drawdowns."
            )
        if secondary:
            summary_parts.append(
                f"Secondary concerns include {', '.join(sec_readable)}."
            )
    elif secondary:
        # No dominant drivers — explain that risk is distributed
        if "concentration_risk" not in secondary and top3w is not None and top3w < 0.55:
            # Concentration is low — emphasize this
            summary_parts.append(
                f"Overall portfolio risk is {overall_level}."
            )
            if beta is not None and beta > 1:
                summary_parts.append(
                    f"Risk is primarily driven by elevated market beta ({beta:.2f}) and "
                    f"{'high-volatility style exposure' if 'high-volatility' in style_tags else 'moderate style exposure'}. "
                    f"Position concentration is not a primary concern."
                )
            else:
                summary_parts.append(
                    f"Risk is moderately distributed across {', '.join(sec_readable[:3])}."
                )
        else:
            summary_parts.append(
                f"Overall portfolio risk is {overall_level}, with moderate exposure to "
                f"{', '.join(sec_readable[:3])}."
            )
    else:
        summary_parts.append(
            f"Overall portfolio risk appears low ({overall_level}) across all analyzed dimensions."
        )

    if available < len(all_results):
        missing = len(all_results) - available
        summary_parts.append(
            f"Note: {missing} dimension(s) could not be fully assessed due to missing data."
        )

    summary = " ".join(summary_parts)

    return {
        "overall_risk_level":   overall_level,
        "dominant_drivers":     dominant,
        "secondary_drivers":    secondary,
        "summary":              summary,
        "risk_score":           total_score,
        "available_dimensions": available,
    }


# ── 7. Proxy Factor Exposure Regression ───────────────────────────────────────

# Factor definitions.  VIX is listed as a future extension — commented out
# until ^VIX daily data is reliably available in the pipeline.
_FACTOR_DEFS: list[dict] = [
    {"ticker": "SPY", "label": "Market"},
    {"ticker": "QQQ", "label": "Growth / Technology"},
    {"ticker": "TLT", "label": "Duration / Rates"},
    # TODO: Add VIX daily changes when ^VIX data is in the pipeline.
    # {"ticker": "^VIX", "label": "Volatility Shock", "transform": "diff"}
]

_MIN_OBS = 60   # minimum overlapping days required for a stable regression


def _interpret_factor(ticker: str, beta: float, significant: bool) -> str:
    """Return a plain-English interpretation for a single factor coefficient."""
    if not significant:
        return "No clear sensitivity detected"

    if ticker == "SPY":
        if beta > 1.2:   return "Elevated market sensitivity"
        if beta > 0.8:   return "Broad market exposure"
        if beta > 0:     return "Defensive market positioning"
        return "Inverse market exposure"

    if ticker == "QQQ":
        if beta > 0.3:   return "Growth / technology tilt"
        if beta > 0:     return "Mild growth tilt"
        if beta < -0.3:  return "Inverse growth / technology exposure"
        return "Mild inverse growth exposure"

    if ticker == "TLT":
        if beta > 0.15:  return "Positive duration exposure (benefits from falling rates)"
        if beta < -0.15: return "Negative duration exposure (vulnerable to rising rates)"
        return "Minimal duration sensitivity detected"

    if ticker == "^VIX":
        if beta < -0.5:  return "Vulnerable to volatility spikes"
        if beta > 0.5:   return "Positive volatility exposure (hedged against spikes)"
        return "Mild volatility sensitivity"

    return "Detectable sensitivity"


def calculate_factor_regression(
    port_returns: pd.Series,
    returns_df: pd.DataFrame,
) -> dict[str, Any]:
    """
    Proxy Factor Exposure Regression: OLS of portfolio daily returns on
    market proxy ETF returns.

    Model
    -----
    portfolio_return(t) = α + β₁·SPY(t) + β₂·QQQ(t) + β₃·TLT(t) + ε(t)

    Proxy factor definitions
    ------------------------
    SPY = broad equity market proxy
    QQQ = growth / technology proxy
    TLT = duration / rates proxy  (NOT a direct 10Y Treasury yield measure;
          captures rate-regime sensitivity directionally via bond ETF returns)

    Returns per-factor: beta, t-stat, p-value, plus R², adj-R², N, VIF.
    Only factors with p < 0.05 are flagged as statistically significant.

    IMPORTANT: This is proxy-based regression using accessible market ETF
    return series. It is not formal academic factor modeling. Each proxy
    captures a specific market regime — it does not decompose into long-short
    constructed portfolios or control for any specific risk premia.

    VIX proxy (volatility-shock sensitivity) is a planned future extension.
    See _FACTOR_DEFS for the commented-out VIX entry.
    """
    try:
        from scipy import stats as _sp

        # ── Load factor series ─────────────────────────────────────────────
        factor_series: dict[str, pd.Series] = {}
        missing: list[str] = []

        for fd in _FACTOR_DEFS:
            t = fd["ticker"]
            s = _load_benchmark(t, returns_df)
            if s is None or s.empty:
                missing.append(t)
            else:
                factor_series[t] = s

        if len(factor_series) < 2:
            return {
                "available": False,
                "reason":    "Fewer than 2 factor series available — regression cannot run.",
                "factors":   [], "r_squared": None, "adj_r_squared": None,
                "n_obs": 0, "condition_number": None, "missing_factors": missing,
                "warnings": [], "model_note": "",
            }

        # ── Align on common dates ──────────────────────────────────────────
        common = port_returns.index
        for s in factor_series.values():
            common = common.intersection(s.index)
        common = common.sort_values().dropna()

        if len(common) < _MIN_OBS:
            return {
                "available": False,
                "reason":    f"Only {len(common)} overlapping observations — need ≥{_MIN_OBS}.",
                "factors":   [], "r_squared": None, "adj_r_squared": None,
                "n_obs":     int(len(common)), "condition_number": None,
                "missing_factors": missing, "warnings": [], "model_note": "",
            }

        y = port_returns.loc[common].values.astype(float)

        factor_names = list(factor_series.keys())
        X_factors = np.column_stack(
            [factor_series[t].loc[common].values.astype(float) for t in factor_names]
        )
        X = np.column_stack([np.ones(len(y)), X_factors])   # prepend intercept
        n, k = X.shape

        # ── OLS ───────────────────────────────────────────────────────────
        try:
            betas, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        except np.linalg.LinAlgError:
            return {
                "available": False,
                "reason":    "Matrix inversion failed — factors may be perfectly collinear.",
                "factors":   [], "r_squared": None, "adj_r_squared": None,
                "n_obs": int(n), "condition_number": None,
                "missing_factors": missing, "warnings": [], "model_note": "",
            }

        y_hat     = X @ betas
        residuals = y - y_hat
        ss_res    = float(np.sum(residuals ** 2))
        ss_tot    = float(np.sum((y - np.mean(y)) ** 2))
        r_sq      = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        adj_r_sq  = 1.0 - (1.0 - r_sq) * (n - 1) / (n - k) if n > k else 0.0

        # Standard errors (homoscedastic OLS; sufficient for this use-case)
        s2 = ss_res / (n - k) if n > k else 0.0
        try:
            cov_b = s2 * np.linalg.inv(X.T @ X)
            se    = np.sqrt(np.clip(np.diag(cov_b), 0, None))
        except np.linalg.LinAlgError:
            se = np.full(k, np.nan)

        t_vals = betas / np.where(se > 0, se, np.nan)
        p_vals = 2.0 * _sp.t.sf(np.abs(t_vals), df=n - k)

        # ── Multicollinearity check ────────────────────────────────────────
        cond = float(np.linalg.cond(X_factors))
        multicollinear = cond > 30.0

        # ── Per-factor results (skip intercept at index 0) ─────────────────
        factor_results: list[dict] = []
        for fd in _FACTOR_DEFS:
            t = fd["ticker"]
            if t not in factor_names:
                continue
            fi  = factor_names.index(t) + 1   # +1 offset for intercept
            b   = round(float(betas[fi]),  4)
            tv  = round(float(t_vals[fi]), 3)
            pv  = round(float(p_vals[fi]), 4)
            sig = bool(pv < 0.05)

            factor_results.append({
                "ticker":         t,
                "label":          fd["label"],
                "beta":           b,
                "t_stat":         tv,
                "p_value":        pv,
                "significant":    sig,
                "interpretation": _interpret_factor(t, b, sig),
            })

        # Intercept row (alpha)
        intercept = {
            "beta":    round(float(betas[0]),  6),
            "t_stat":  round(float(t_vals[0]), 3),
            "p_value": round(float(p_vals[0]), 4),
        }

        # ── VIF-based multicollinearity check ─────────────────────────────
        # VIF > 10 indicates collinearity is distorting individual coefficients.
        vifs: dict[str, float] = {}
        for fi_idx, fi_name in enumerate(factor_names):
            others = np.delete(X_factors, fi_idx, axis=1)
            X_vif  = np.column_stack([np.ones(n), others])
            b_vif, _, _, _ = np.linalg.lstsq(X_vif, X_factors[:, fi_idx], rcond=None)
            yh_vif   = X_vif @ b_vif
            ss_r     = float(np.sum((X_factors[:, fi_idx] - yh_vif) ** 2))
            ss_t     = float(np.sum((X_factors[:, fi_idx] - X_factors[:, fi_idx].mean()) ** 2))
            r2_vif   = 1.0 - ss_r / ss_t if ss_t > 0 else 0.0
            vifs[fi_name] = round(1.0 / (1.0 - r2_vif) if r2_vif < 0.9999 else 999.0, 1)

        high_vif_factors = [t for t, v in vifs.items() if v > 10]
        multicollinear   = bool(high_vif_factors)

        # When QQQ dominates and SPY comes out negative, that's a VIF artifact.
        # Flag it explicitly so the user isn't misled.
        spy_idx = factor_names.index("SPY") if "SPY" in factor_names else -1
        qqq_idx = factor_names.index("QQQ") if "QQQ" in factor_names else -1
        spy_neg_artifact = (
            spy_idx >= 0 and qqq_idx >= 0
            and float(betas[spy_idx + 1]) < -0.05
            and float(betas[qqq_idx + 1]) > 0.5
        )
        if spy_neg_artifact:
            # Override the SPY interpretation to avoid misleading "inverse market" label
            for fr in factor_results:
                if fr["ticker"] == "SPY":
                    fr["interpretation"] = (
                        "Negative coefficient is a collinearity artifact — "
                        "QQQ absorbs the market signal in this regression"
                    )

        warnings: list[str] = []
        if multicollinear:
            vif_str = ", ".join(f"{t} VIF={v}" for t, v in vifs.items() if v > 10)
            warnings.append(
                f"Factor collinearity detected ({vif_str}). "
                "SPY and QQQ are highly correlated — their individual betas are "
                "interdependent and should be read together, not in isolation. "
                "The R² and combined factor betas are more informative than any single coefficient."
            )
        if missing:
            warnings.append(f"Factor data unavailable for: {', '.join(missing)}.")

        return {
            "available":       True,
            "factors":         factor_results,
            "intercept":       intercept,
            "r_squared":       round(r_sq,     4),
            "adj_r_squared":   round(adj_r_sq, 4),
            "n_obs":           int(n),
            "condition_number": round(cond, 1),
            "vif":             vifs,
            "missing_factors": missing,
            "warnings":        warnings,
            "model_note": (
                "Proxy Factor Exposure Regression using market proxy ETF returns. "
                "SPY = broad equity proxy · QQQ = growth/technology proxy · "
                "TLT = duration/rates proxy (not a direct 10Y yield measure). "
                "p < 0.05 indicates statistically detectable sensitivity to a proxy factor. "
                "Volatility-shock sensitivity (VIX proxy) is planned as a future extension."
            ),
        }

    except Exception as exc:
        return {
            "available": False,
            "reason":    f"Regression failed: {str(exc)[:200]}",
            "factors":   [], "r_squared": None, "adj_r_squared": None,
            "n_obs": 0, "condition_number": None,
            "missing_factors": [], "warnings": [], "model_note": "",
        }


# ── Public entry point ─────────────────────────────────────────────────────────

def compute_risk_attribution(
    weights: dict[str, float],
    returns_df: pd.DataFrame | None,
    port_returns: pd.Series | None,
    risk_metrics: dict[str, Any],
    top_risk_contributors: list[dict[str, Any]],
    stress_analysis: list[dict[str, Any]],
    enriched_holdings: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compute all six risk attribution dimensions.
    Never raises — missing data produces risk_level="Unknown".
    """
    df = returns_df if returns_df is not None else pd.DataFrame()
    pr = port_returns if port_returns is not None else pd.Series(dtype=float)

    market       = calculate_market_risk_attribution(weights, df, pr)
    sector       = calculate_sector_concentration(enriched_holdings)
    concentration = calculate_concentration_risk(weights, top_risk_contributors)
    style        = calculate_style_factor_exposure(weights, top_risk_contributors, enriched_holdings, market)
    # Tail receives style context so it can reference growth/beta drivers
    tail         = calculate_tail_risk_attribution(pr, risk_metrics, stress_analysis, style)
    macro        = calculate_macro_risk_exposure(weights, df, pr)
    overall      = generate_risk_driver_summary(market, sector, style, macro, concentration, tail)

    factor_regression = calculate_factor_regression(pr, df)

    return {
        "market_risk":        market,
        "sector_risk":        sector,
        "style_risk":         style,
        "macro_risk":         macro,
        "concentration_risk": concentration,
        "tail_risk":          tail,
        "overall":            overall,
        "factor_regression":  factor_regression,
    }
