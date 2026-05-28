"""
FastAPI backend for the AI Portfolio Risk Assistant.

Run with:  uvicorn api.main:app --host 0.0.0.0 --port $PORT
"""

import os
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

load_dotenv()

# ── paths ──────────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent.parent
TABLES = BASE / "outputs" / "tables"
OUTPUTS = BASE / "outputs"
SRC = BASE / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# ──────────────────────────────────────────────────────────────────────────────

# ── CORS ───────────────────────────────────────────────────────────────────────
# Add your Vercel frontend URL as FRONTEND_URL in Railway Variables.
# Multiple URLs can be comma-separated in FRONTEND_ORIGIN as a fallback.
_ALLOWED_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://localhost:3002",
    "http://localhost:5173",
    # Deployed Vercel frontend (hardcoded as safe fallback)
    "https://ai-portfolio-risk-assistant-9sy31ue8b-stephanie-xie-s-projects.vercel.app",
]

# FRONTEND_URL — single production URL set in Railway Variables
_frontend_url = os.environ.get("FRONTEND_URL", "").strip()
if _frontend_url:
    _ALLOWED_ORIGINS.append(_frontend_url)

# FRONTEND_ORIGIN — comma-separated list or * (legacy support)
_env_origin = os.environ.get("FRONTEND_ORIGIN", "").strip()
if _env_origin == "*":
    _ALLOWED_ORIGINS = ["*"]
elif _env_origin:
    for _o in _env_origin.split(","):
        _o = _o.strip()
        if _o and _o not in _ALLOWED_ORIGINS:
            _ALLOWED_ORIGINS.append(_o)

ALLOWED_ORIGINS = list(dict.fromkeys(_ALLOWED_ORIGINS))
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Portfolio Risk API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,   # no cookies/auth — False is compatible with wildcard too
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── file helpers ───────────────────────────────────────────────────────────────

def _csv_to_records(path: Path) -> list[dict]:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path.name}")
    return pd.read_csv(path).to_dict(orient="records")


def _read_markdown(path: Path) -> str:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path.name}")
    return path.read_text(encoding="utf-8")


# ── root ───────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "name": "Portfolio Risk API",
        "version": "2.0.0",
        "status": "ok",
        "endpoints": ["/health", "/analyze-portfolio", "/generate-risk-summary"],
    }


# ── static MVP endpoints (unchanged) ──────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/database/health")
def database_health():
    """
    Check that DATABASE_URL is set and that a simple query succeeds.
    Returns {"status": "ok", "database": "connected"} on success.
    """
    import db as _db
    if not _db.is_configured():
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL is not set in environment variables.",
        )
    try:
        from sqlalchemy import text as _text
        with _db.get_db_session() as conn:
            conn.execute(_text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {exc}",
        )
    return {"status": "ok", "database": "connected"}


@app.get("/risk-summary")
def risk_summary():
    return _csv_to_records(TABLES / "risk_summary.csv")


@app.get("/top-risk-contributors")
def top_risk_contributors():
    return _csv_to_records(TABLES / "top_risk_contributors.csv")


@app.get("/stress-summary")
def stress_summary():
    return _csv_to_records(TABLES / "stress_summary.csv")


@app.get("/stress-asset-contributions")
def stress_asset_contributions():
    return _csv_to_records(TABLES / "stress_asset_contributions.csv")


@app.get("/company-risk-evidence")
def company_risk_evidence():
    return {"markdown": _read_markdown(OUTPUTS / "company_risk_evidence.md")}


@app.get("/risk-memo")
def risk_memo():
    return {"markdown": _read_markdown(OUTPUTS / "sample_memo.md")}


@app.post("/refresh-company-risk-evidence")
def refresh_company_risk_evidence():
    try:
        from company_risk_summary import build_company_risk_evidence
        markdown = build_company_risk_evidence()
        out = OUTPUTS / "company_risk_evidence.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── provider-layer endpoints ───────────────────────────────────────────────────

@app.get("/company-profile/{ticker}")
def company_profile(ticker: str):
    from providers.market_data_provider import get_company_profile
    result = get_company_profile(ticker)
    if result.get("error") and not result.get("name"):
        raise HTTPException(status_code=404, detail=result["error"])

    # Persist to database — failure must not break the response
    if result.get("name"):
        try:
            import db_repository as _repo
            _repo.upsert_company({**result, "ticker": ticker})
        except Exception as exc:
            result["db_warning"] = f"Database write failed: {exc}"

    return result


@app.get("/price-history/{ticker}")
def price_history(ticker: str):
    from providers.market_data_provider import get_price_history
    result = get_price_history(ticker)
    if result.get("error") and result["count"] == 0:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/sec-cik/{ticker}")
def sec_cik(ticker: str):
    from providers.sec_edgar_provider import get_cik_for_ticker
    result = get_cik_for_ticker(ticker)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ── dynamic SEC + Qdrant endpoints ────────────────────────────────────────────

@app.get("/sec-risk-factors/{ticker}")
def sec_risk_factors(ticker: str, force: bool = False):
    """
    Extract (or return cached) Item 1A Risk Factors from the latest 10-K.
    Saves the full markdown to data/documents/{TICKER}/10k_risk_factors.md.
    Pass ?force=true to re-download and re-extract even if cached.
    """
    from providers.sec_risk_factors import extract_risk_factors
    result = extract_risk_factors(ticker, force=force)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])

    # Persist SEC filing metadata to database — failure must not break response
    try:
        import db_repository as _repo
        _repo.insert_sec_filing({
            "ticker":               ticker.upper().strip(),
            "filing_type":          "10-K",
            "filing_date":          result.get("filing_date", ""),
            "accession_number":     result.get("accession_number", ""),
            "source_url":           result.get("source_url", ""),
            "risk_factors_path":    result.get("path", ""),
            "risk_factors_extracted": True,
            "qdrant_ingested":      False,
        })
    except Exception as exc:
        result["db_warning"] = f"Database write failed: {exc}"

    return result


@app.post("/ingest-risk-factors/{ticker}")
def ingest_risk_factors(ticker: str):
    """
    Chunk, embed, and upsert the ticker's risk factors markdown into Qdrant Cloud.
    Run GET /sec-risk-factors/{ticker} first to ensure the markdown file exists.
    Returns the number of chunks ingested.
    """
    try:
        import qdrant_ingestion
        result = qdrant_ingestion.ingest_ticker_risk_factors(ticker)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    # Persist Qdrant ingestion status + chunk metadata to database
    db_write_warnings: list[str] = []
    try:
        import db_repository as _repo

        # Read frontmatter from the markdown file to get accession_number
        from pathlib import Path as _Path
        _t = ticker.upper().strip()
        _md_path = BASE / "data" / "documents" / _t / "10k_risk_factors.md"
        _accession = ""
        _filing_date = ""
        _source_url = ""
        if _md_path.exists():
            _text = _md_path.read_text(encoding="utf-8")
            if _text.startswith("---"):
                _end = _text.find("---", 3)
                if _end != -1:
                    for _line in _text[3:_end].split("\n"):
                        if ":" in _line:
                            _k, _, _v = _line.partition(":")
                            _k = _k.strip(); _v = _v.strip()
                            if _k == "accession_number": _accession = _v
                            if _k == "filing_date":      _filing_date = _v
                            if _k == "source_url":       _source_url = _v

        if _accession:
            _repo.update_sec_filing_qdrant_status(_accession, qdrant_ingested=True)

        # Bulk insert rag_document metadata for each ingested chunk
        _collection = qdrant_ingestion.COLLECTION_NAME
        import uuid as _uuid
        _ns = qdrant_ingestion._CHUNK_NS
        _chunks_n = result.get("chunks_ingested", 0)
        _rag_rows = [
            {
                "ticker":            _t,
                "qdrant_collection": _collection,
                "qdrant_point_id":   str(_uuid.uuid5(_ns, f"{_t}_10k_risk_factors_{i}")),
                "chunk_id":          f"{_t}_10k_risk_factors_{i}",
                "source_type":       "10k_risk_factors",
                "source_file":       "10k_risk_factors.md",
                "filing_date":       _filing_date,
                "accession_number":  _accession,
                "source_url":        _source_url,
            }
            for i in range(_chunks_n)
        ]
        written = _repo.insert_rag_documents_bulk(_rag_rows)
        result["rag_documents_written"] = written

    except Exception as exc:
        db_write_warnings.append(f"Database write failed: {exc}")

    if db_write_warnings:
        result["db_write_warnings"] = db_write_warnings

    return result


@app.get("/company-risk-query")
def company_risk_query(
    ticker: str = Query(..., description="Ticker symbol to filter by"),
    query: str = Query(..., description="Natural-language risk query"),
    top_k: int = Query(5, ge=1, le=20, description="Number of results to return"),
):
    """
    Semantic search over ingested company risk documents in Qdrant.
    """
    try:
        import qdrant_ingestion
        hits = qdrant_ingestion.retrieve_company_risks(
            query=query,
            tickers=[ticker] if ticker else None,
            top_k=top_k,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"ticker": ticker, "query": query, "top_k": top_k, "results": hits}


# ── Portfolio analysis ─────────────────────────────────────────────────────────

class Holding(BaseModel):
    """
    A single portfolio position.

    Exactly one of weight / amount / shares must be provided, matching
    the PortfolioInput.input_mode field.  The API validates this at
    request time rather than in the model so that the model stays
    flexible for all three modes.
    """
    ticker: str
    weight: Optional[float] = None   # input_mode="weights" — 0-1 or 0-100
    amount: Optional[float] = None   # input_mode="amounts" — dollar value
    shares: Optional[float] = None   # input_mode="shares"  — share count

    @field_validator("ticker")
    @classmethod
    def normalise_ticker(cls, v: str) -> str:
        return v.upper().strip()


class PortfolioInput(BaseModel):
    holdings: list[Holding]

    # ── Input mode ──────────────────────────────────────────────────────────
    input_mode: str = "weights"           # "weights" | "amounts" | "shares"

    # Used only when input_mode = "amounts"
    total_portfolio_value:    Optional[float] = None
    treat_unallocated_as_cash: bool           = False

    # ── Optional database-save fields ───────────────────────────────────────
    portfolio_name:   Optional[str] = None
    description:      Optional[str] = None
    portfolio_goal:   Optional[str] = None
    save_to_database: bool          = False

    # ── Optional AI summary ──────────────────────────────────────────────────
    generate_ai_summary: bool = False

    @field_validator("holdings")
    @classmethod
    def at_least_one(cls, v: list[Holding]) -> list[Holding]:
        if not v:
            raise ValueError("holdings list cannot be empty")
        return v


# ── Weight resolution helper ────────────────────────────────────────────────

def _resolve_to_weights(
    body: PortfolioInput,
) -> tuple[dict[str, float], list[str], list[str]]:
    """
    Convert any input_mode to a normalized weight dict {ticker: 0-1 float}.

    Returns
    -------
    (norm_weights, warnings, errors)
    errors is non-empty when the request is semantically invalid.
    """
    mode     = body.input_mode
    holdings = body.holdings
    warnings: list[str] = []

    # ── weights mode (existing behavior) ────────────────────────────────────
    if mode == "weights":
        for h in holdings:
            if h.weight is None or h.weight <= 0:
                return {}, [], [
                    f"Holding '{h.ticker}': weight must be positive in weights mode."
                ]

        raw_total = sum(h.weight for h in holdings)  # type: ignore[operator]

        if 95.0 <= raw_total <= 105.0:
            scale = 100.0
        elif 0.95 <= raw_total <= 1.05:
            scale = 1.0
        else:
            return {}, [], [
                f"Weights sum to {raw_total:.4f}. "
                "Expected weights summing to ≈ 1.0 (e.g. 0.25) or ≈ 100 (e.g. 25)."
            ]

        raw_map = {h.ticker: h.weight / scale for h in holdings}  # type: ignore[operator]
        w_sum   = sum(raw_map.values())
        return {t: round(w / w_sum, 8) for t, w in raw_map.items()}, warnings, []

    # ── amounts mode ────────────────────────────────────────────────────────
    if mode == "amounts":
        for h in holdings:
            if h.amount is None or h.amount <= 0:
                return {}, [], [
                    f"Holding '{h.ticker}': amount must be positive in amounts mode."
                ]

        total_entered = sum(h.amount for h in holdings)  # type: ignore[operator]
        total_pv      = body.total_portfolio_value

        if total_pv is not None:
            if total_pv <= 0:
                return {}, [], ["total_portfolio_value must be positive."]
            if total_pv < total_entered - 0.01:
                return {}, [], [
                    f"total_portfolio_value ({total_pv:,.2f}) is less than "
                    f"the sum of entered amounts ({total_entered:,.2f})."
                ]
            unallocated = max(0.0, total_pv - total_entered)
            denominator = total_pv
        else:
            unallocated = 0.0
            denominator = total_entered

        raw_map: dict[str, float] = {
            h.ticker: h.amount / denominator  # type: ignore[operator]
            for h in holdings
        }

        if unallocated > 0.01:
            if body.treat_unallocated_as_cash:
                raw_map["CASH"] = unallocated / denominator
            else:
                warnings.append(
                    f"Unallocated amount (${unallocated:,.2f}) was excluded from risk "
                    "calculations. Total portfolio risk may be understated."
                )

        w_sum = sum(raw_map.values())
        return {t: round(w / w_sum, 8) for t, w in raw_map.items()}, warnings, []

    # ── shares mode ─────────────────────────────────────────────────────────
    if mode == "shares":
        import dynamic_portfolio as _dp

        for h in holdings:
            if h.shares is None or h.shares <= 0:
                return {}, [], [
                    f"Holding '{h.ticker}': shares must be positive in shares mode."
                ]

        market_values: dict[str, float] = {}
        failed_price:  list[str]        = []

        for h in holdings:
            price = _dp.get_latest_price(h.ticker)
            if price is None or price <= 0:
                failed_price.append(h.ticker)
            else:
                market_values[h.ticker] = h.shares * price  # type: ignore[operator]

        if not market_values:
            return {}, [], [
                f"Could not fetch prices for: {', '.join(failed_price)}. "
                "No holdings could be priced. Check ticker symbols and connectivity."
            ]

        if failed_price:
            warnings.append(
                f"Could not fetch price for {', '.join(failed_price)}. "
                "These holdings were excluded and remaining weights were renormalized."
            )

        total_value = sum(market_values.values())
        raw         = {t: v / total_value for t, v in market_values.items()}
        w_sum       = sum(raw.values())
        return {t: round(w / w_sum, 8) for t, w in raw.items()}, warnings, []

    return {}, [], [f"Unknown input_mode: '{mode}'. Use 'weights', 'amounts', or 'shares'."]


@app.post("/analyze-portfolio")
def analyze_portfolio(body: PortfolioInput):
    """
    Validate holdings, fetch company profiles, and compute dynamic portfolio
    risk metrics from historical price data (yfinance, 2018-01-01 to today).

    Accepts weights as decimals summing to ≈ 1.0 (e.g. 0.25)
    or as percentages summing to ≈ 100 (e.g. 25). If the sum is not
    within 5% of either target a 422 error is returned.

    This endpoint never returns buy/sell recommendations.
    """
    from providers.market_data_provider import get_company_profile
    import dynamic_portfolio

    # ── resolve input mode → normalized weights ──────────────────────────────
    norm_weights, mode_warnings, mode_errors = _resolve_to_weights(body)

    if mode_errors:
        raise HTTPException(status_code=422, detail=" ".join(mode_errors))

    # Build a synthetic Holding list that always has weight set (for downstream code)
    resolved_holdings = [
        Holding(ticker=t, weight=round(w * 100, 6))   # store as 0-100 internally
        for t, w in norm_weights.items()
    ]

    # ── company profiles (errors are isolated — never abort the endpoint) ────
    enriched_holdings = []
    for h in resolved_holdings:
        try:
            if h.ticker == "CASH":
                # Synthetic asset — no external data needed
                profile = {
                    "ticker": "CASH",
                    "name": "Cash / Money Market",
                    "sector": "Cash",
                    "industry": "Cash Equivalent",
                    "source": "synthetic",
                }
            else:
                profile = get_company_profile(h.ticker)
        except Exception as exc:
            profile = {"error": str(exc)}

        enriched_holdings.append(
            {
                "ticker": h.ticker,
                "weight": norm_weights[h.ticker],
                "weight_pct": f"{norm_weights[h.ticker] * 100:.1f}%",
                "profile": {
                    "name":         profile.get("name", ""),
                    "sector":       profile.get("sector", ""),
                    "industry":     profile.get("industry", ""),
                    "exchange":     profile.get("exchange", ""),
                    "market_cap":   profile.get("market_cap", ""),
                    "pe_ratio":     profile.get("pe_ratio", ""),
                    "week_52_high": profile.get("week_52_high", ""),
                    "week_52_low":  profile.get("week_52_low", ""),
                    "source":       profile.get("source", ""),
                    "profile_error": profile.get("error"),
                },
            }
        )

    # ── dynamic risk analysis ────────────────────────────────────────────────
    try:
        analysis = dynamic_portfolio.analyze_portfolio(
            [{"ticker": t, "weight": w} for t, w in norm_weights.items()]
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Risk calculation failed: {exc}",
        )

    total_weight = round(sum(norm_weights.values()), 6)

    # ── optional database save ───────────────────────────────────────────────
    portfolio_id: Optional[str] = None
    analysis_id:  Optional[str] = None
    db_warnings:  list[str]     = []

    if body.save_to_database:
        try:
            import db_repository as _repo

            # Step 1: upsert companies FIRST — portfolio_holdings and sec_filings
            # both have FK → companies(ticker), so the company row must exist first.
            for eh in enriched_holdings:
                try:
                    _repo.upsert_company({
                        "ticker":      eh["ticker"],
                        "name":        eh["profile"].get("name"),
                        "sector":      eh["profile"].get("sector"),
                        "industry":    eh["profile"].get("industry"),
                        "exchange":    eh["profile"].get("exchange"),
                        "market_cap":  eh["profile"].get("market_cap"),
                        "pe_ratio":    eh["profile"].get("pe_ratio"),
                        "week_52_high": eh["profile"].get("week_52_high"),
                        "week_52_low":  eh["profile"].get("week_52_low"),
                        "source":      eh["profile"].get("source"),
                    })
                except Exception as exc:
                    db_warnings.append(f"Company upsert failed for {eh['ticker']}: {exc}")

            # Step 2: create portfolio and holdings
            portfolio_id = _repo.create_portfolio(
                portfolio_name=body.portfolio_name or "Unnamed Portfolio",
                description=body.description,
                portfolio_goal=body.portfolio_goal,
            )
            _repo.upsert_portfolio_holdings(
                portfolio_id,
                [{"ticker": t, "weight": w} for t, w in norm_weights.items()],
            )

            # Step 3: save analysis results
            analysis_id = _repo.insert_analysis_run(
                request_holdings=[{"ticker": t, "weight": w} for t, w in norm_weights.items()],
                risk_metrics=analysis["risk_metrics"],
                correlation_matrix=analysis["correlation_matrix"],
                top_risk_contributors=analysis["top_risk_contributors"],
                stress_analysis=analysis["stress_analysis"],
                company_risk_evidence=analysis["company_risk_evidence"],
                warnings=analysis["warnings"],
                portfolio_id=portfolio_id,
                status="completed",
            )
        except Exception as exc:
            db_warnings.append(f"Database save failed: {exc}")

    all_warnings = mode_warnings + analysis["warnings"] + db_warnings

    # ── Optional AI summary ──────────────────────────────────────────────────
    import logging as _logging
    _ai_logger = _logging.getLogger("ai_summary")

    ai_summary = None
    if body.generate_ai_summary:
        try:
            import ai_summary as _ai

            ai_input = {
                "holdings":              enriched_holdings,
                "risk_metrics":          analysis["risk_metrics"],
                "top_risk_contributors": analysis["top_risk_contributors"],
                "stress_analysis":       analysis["stress_analysis"],
                "company_risk_evidence": analysis["company_risk_evidence"],
                "warnings":              all_warnings,
            }
            result_ai = _ai.generate_portfolio_risk_summary(ai_input)

            if "error" in result_ai:
                reason = result_ai["error"]
                _ai_logger.warning("AI summary returned error: %s", reason)
                # Truncate to keep response clean; never expose key content
                safe = reason[:160] if len(reason) > 160 else reason
                all_warnings.append(f"AI summary could not be generated: {safe}")
                ai_summary = None
            else:
                ai_summary = result_ai

        except Exception as _exc:
            _ai_logger.exception("AI summary raised an unhandled exception")
            safe = f"{type(_exc).__name__}: {str(_exc)[:120]}"
            all_warnings.append(f"AI summary could not be generated: {safe}")

    return {
        "holdings": enriched_holdings,
        "total_weight": total_weight,
        "total_weight_pct": f"{total_weight * 100:.1f}%",
        "dynamic_risk_metrics_status": "implemented",
        "risk_metrics": analysis["risk_metrics"],
        "correlation_matrix": analysis["correlation_matrix"],
        "top_risk_contributors": analysis["top_risk_contributors"],
        "stress_analysis": analysis["stress_analysis"],
        "company_risk_evidence": analysis["company_risk_evidence"],
        "failed_tickers": analysis["failed_tickers"],
        "warnings": all_warnings,
        "portfolio_id": portfolio_id,
        "analysis_id":  analysis_id,
        "ai_summary": ai_summary,
        "disclaimer": (
            "This tool is for educational and research purposes only. "
            "It does not provide investment advice or trading recommendations."
        ),
    }


# ── AI summary diagnostics endpoint ───────────────────────────────────────────

@app.get("/ai-summary-status")
def ai_summary_status():
    """
    Lightweight check: is the AI summary layer configured and reachable?
    Never returns the API key value.
    """
    import ai_summary as _ai   # noqa: F401 — just checks import
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    configured = bool(api_key)
    key_hint   = f"...{api_key[-4:]}" if configured else "(not set)"

    try:
        import openai as _oai
        sdk_version = getattr(_oai, "__version__", "unknown")
    except ImportError:
        sdk_version = "NOT INSTALLED"

    return {
        "openai_configured": configured,
        "openai_key_hint":   key_hint,
        "openai_model":      model,
        "openai_sdk_version": sdk_version,
        "note": "Call POST /generate-risk-summary with a real analysis payload to test end-to-end.",
    }


# ── Standalone AI risk summary endpoint ────────────────────────────────────────

class AnalysisResultInput(BaseModel):
    """Accepts the same shape as /analyze-portfolio response for standalone summarization."""
    risk_metrics:           dict
    holdings:               list     = []
    top_risk_contributors:  list     = []
    stress_analysis:        list     = []
    company_risk_evidence:  dict     = {}
    warnings:               list     = []


@app.post("/generate-risk-summary")
def generate_risk_summary(body: AnalysisResultInput):
    """
    Generate an AI risk summary from a pre-computed analysis result.

    Accepts the same JSON shape as the /analyze-portfolio response.
    Requires OPENAI_API_KEY to be set on the backend.
    This endpoint never returns investment advice or trading recommendations.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured on the server.",
        )

    try:
        import ai_summary as _ai

        result = _ai.generate_portfolio_risk_summary(body.model_dump())
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI summary failed: {exc}")
