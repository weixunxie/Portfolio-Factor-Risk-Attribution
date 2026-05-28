"""
src/ai_summary.py

AI-powered portfolio risk summary layer.

The LLM is used ONLY to narrate already-computed quantitative results in plain
English.  It does not:
  - calculate metrics
  - fetch market data
  - predict prices or future returns
  - provide investment advice or trading recommendations
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ── System prompt ──────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a portfolio risk analyst assistant. \
Your sole task is to narrate already-computed portfolio risk analytics in clear, \
concise, professional English — similar to a brief analyst risk memo.

STRICT RULES — you must never violate these:
1. Only use numbers and facts from the JSON input provided. Do not calculate, \
   estimate, or invent any values.
2. Do not provide investment advice of any kind.
3. Do not recommend buying, selling, holding, rebalancing, or trading any security.
4. Do not predict future performance, prices, or returns.
5. Never use the words: buy, sell, hold, outperform, underperform, undervalued, \
   overvalued, price target, expected return, recommendation, or alpha.
6. Be concise and precise. Do not pad the response.
7. When company risk evidence is missing or limited for a ticker, \
   acknowledge that explicitly rather than speculating.
8. Focus exclusively on: risk concentration, volatility, drawdown, \
   historical stress-period behavior, and source-grounded company risk disclosures.
9. Always return valid JSON matching the schema described by the user prompt.
"""


# ── Prompt builder ─────────────────────────────────────────────────────────────

def _build_user_prompt(analysis_result: dict[str, Any]) -> str:
    """Compress the analysis result into a compact JSON payload for the prompt."""

    risk_metrics = analysis_result.get("risk_metrics") or {}
    contributors = (analysis_result.get("top_risk_contributors") or [])[:5]
    stress       = analysis_result.get("stress_analysis") or []
    evidence     = analysis_result.get("company_risk_evidence") or {}
    warnings     = analysis_result.get("warnings") or []
    holdings     = analysis_result.get("holdings") or []

    # ── simplify holdings ──────────────────────────────────────────────────
    slim_holdings = [
        {"ticker": h.get("ticker"), "weight_pct": h.get("weight_pct")}
        for h in holdings[:12]
    ]

    # ── simplify risk metrics (already in decimal form 0-1) ───────────────
    def pct(val: float | None) -> str:
        if val is None:
            return "N/A"
        return f"{val * 100:.2f}%"

    slim_metrics = {
        "annualized_return":     pct(risk_metrics.get("annualized_return")),
        "annualized_volatility": pct(risk_metrics.get("annualized_volatility")),
        "sharpe_ratio":          round(risk_metrics.get("sharpe_ratio") or 0, 2),
        "max_drawdown":          pct(risk_metrics.get("max_drawdown")),
        "var_95":                pct(risk_metrics.get("var_95")),
        "cvar_95":               pct(risk_metrics.get("cvar_95")),
        "data_start":            risk_metrics.get("data_start"),
        "data_end":              risk_metrics.get("data_end"),
    }

    # ── simplify contributors ──────────────────────────────────────────────
    slim_contrib = [
        {
            "ticker":              c.get("ticker"),
            "weight_pct":          pct(c.get("weight")),
            "annualized_vol_pct":  pct(c.get("annualized_volatility")),
            "wt_vol_contrib_pct":  pct(c.get("weight_volatility_contribution")),
            "corr_with_portfolio": round(c.get("correlation_with_portfolio") or 0, 3),
        }
        for c in contributors
    ]

    # ── simplify stress ────────────────────────────────────────────────────
    slim_stress = []
    for s in stress:
        cr  = s.get("portfolio_cumulative_return")
        mdd = s.get("portfolio_max_drawdown")
        worst = [
            {
                "ticker":        w.get("ticker"),
                "contribution":  pct(w.get("weighted_contribution")),
            }
            for w in (s.get("worst_contributors") or [])[:2]
        ]
        slim_stress.append({
            "period":              s.get("period"),
            "cumulative_return":   pct(cr)  if cr  is not None else "N/A",
            "max_drawdown":        pct(mdd) if mdd is not None else "N/A",
            "worst_contributors":  worst,
        })

    # ── simplify evidence ──────────────────────────────────────────────────
    slim_evidence: dict[str, str] = {}
    for ticker, data in evidence.items():
        if isinstance(data, list) and data:
            # Take the first hit's text, capped at 400 chars
            text = (data[0].get("text") or "")[:400]
            slim_evidence[ticker] = text if text else "(no text available)"
        elif isinstance(data, dict):
            slim_evidence[ticker] = data.get("message", "(no evidence)")
        else:
            slim_evidence[ticker] = "(no evidence)"

    payload = {
        "holdings":               slim_holdings,
        "risk_metrics":           slim_metrics,
        "top_risk_contributors":  slim_contrib,
        "stress_analysis":        slim_stress,
        "company_risk_evidence":  slim_evidence,
        "warnings":               warnings,
    }

    schema = (
        '{\n'
        '  "summary": "<2-4 sentence overview of portfolio risk profile>",\n'
        '  "key_risks": ["<risk 1>", "<risk 2>", "<risk 3>"],\n'
        '  "stress_takeaway": "<1-2 sentences on historical stress behavior>",\n'
        '  "evidence_takeaway": "<1-2 sentences on company-level SEC risk evidence, '
        'or note if limited>",\n'
        '  "disclaimer": "<leave this field empty — it will be set by the server>"\n'
        '}'
    )

    return (
        "Based on the already-computed portfolio risk analytics below, "
        "write a concise analyst-style risk summary.\n\n"
        f"Return ONLY a valid JSON object matching this schema:\n{schema}\n\n"
        f"Input analytics:\n```json\n{json.dumps(payload, indent=2)}\n```"
    )


# ── Main function ──────────────────────────────────────────────────────────────

def generate_portfolio_risk_summary(analysis_result: dict[str, Any]) -> dict[str, Any]:
    """
    Generate a concise AI risk summary from already-computed analysis results.

    The LLM narrates — it never calculates metrics, fetches data, or provides
    investment advice.

    Returns a dict with keys:
        summary, key_risks, stress_takeaway, evidence_takeaway, disclaimer

    On any error, returns {"error": "<message>"} so callers can degrade gracefully.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"error": "OPENAI_API_KEY is not configured."}

    if not analysis_result.get("risk_metrics"):
        return {"error": "risk_metrics missing from analysis_result — cannot generate summary."}

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        user_prompt = _build_user_prompt(analysis_result)

        # Build kwargs defensively — openai SDK v1 uses max_tokens,
        # v2+ may prefer max_completion_tokens.  response_format as a
        # plain dict is accepted by both.
        create_kwargs: dict = {
            "model":           model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature":     0.25,
        }
        # Attempt max_completion_tokens first (v2+); fall back silently
        import inspect as _inspect
        _sig = _inspect.signature(client.chat.completions.create)
        if "max_completion_tokens" in _sig.parameters:
            create_kwargs["max_completion_tokens"] = 900
        else:
            create_kwargs["max_tokens"] = 900

        response = client.chat.completions.create(**create_kwargs)

        raw = response.choices[0].message.content or "{}"
        result: dict[str, Any] = json.loads(raw)

        # Ensure all expected keys exist with sensible defaults
        result.setdefault("summary", "")
        result.setdefault("key_risks", [])
        result.setdefault("stress_takeaway", "")
        result.setdefault("evidence_takeaway", "")

        # Always override the disclaimer — never trust the LLM for this
        result["disclaimer"] = (
            "This summary is for educational and research purposes only. "
            "It does not provide investment advice or trading recommendations."
        )

        return result

    except json.JSONDecodeError as exc:
        logger.error("AI summary JSON decode error: %s", exc)
        return {"error": "AI summary returned malformed JSON."}
    except Exception as exc:
        logger.error("AI summary generation failed: %s", exc)
        # Truncate to avoid leaking internal details
        return {"error": f"AI summary generation failed: {str(exc)[:200]}"}
