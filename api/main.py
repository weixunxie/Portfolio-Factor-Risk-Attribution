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
_default_origins = [
    "http://localhost:3000",
    "http://localhost:3002",   # primary local dev port
    "http://localhost:5173",
]
_env_origin = os.environ.get("FRONTEND_ORIGIN", "")
_extra = [o.strip() for o in _env_origin.split(",") if o.strip()]
ALLOWED_ORIGINS = list(dict.fromkeys(_default_origins + _extra))
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Portfolio Risk API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
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
    ticker: str
    weight: float

    @field_validator("ticker")
    @classmethod
    def normalise_ticker(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("weight")
    @classmethod
    def weight_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("weight must be positive")
        if v > 100:
            raise ValueError("weight cannot exceed 100")
        return round(v, 6)


class PortfolioInput(BaseModel):
    holdings: list[Holding]
    # Optional database-save fields (fully backward-compatible)
    portfolio_name:  Optional[str]  = None
    description:     Optional[str]  = None
    portfolio_goal:  Optional[str]  = None
    save_to_database: bool          = False

    @field_validator("holdings")
    @classmethod
    def at_least_one(cls, v: list[Holding]) -> list[Holding]:
        if not v:
            raise ValueError("holdings list cannot be empty")
        return v


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

    # ── weight validation and normalization ──────────────────────────────────
    raw_total = sum(h.weight for h in body.holdings)

    if 95.0 <= raw_total <= 105.0:
        # Percentage-style input (e.g. 50 + 50 = 100) — convert to decimals
        scale = 100.0
    elif 0.95 <= raw_total <= 1.05:
        scale = 1.0
    else:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Weights sum to {raw_total:.4f}. "
                "Expected weights summing to 1.0 (e.g. 0.25 + 0.75) "
                "or 100 (e.g. 25 + 75). Please adjust your inputs."
            ),
        )

    # Build a normalized weight map that sums exactly to 1.0
    raw_map = {h.ticker: h.weight / scale for h in body.holdings}
    w_sum = sum(raw_map.values())
    norm_weights: dict[str, float] = {t: round(w / w_sum, 8) for t, w in raw_map.items()}

    # ── company profiles (errors are isolated — never abort the endpoint) ────
    enriched_holdings = []
    for h in body.holdings:
        try:
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

            portfolio_id = _repo.create_portfolio(
                portfolio_name=body.portfolio_name or "Unnamed Portfolio",
                description=body.description,
                portfolio_goal=body.portfolio_goal,
            )
            _repo.upsert_portfolio_holdings(
                portfolio_id,
                [{"ticker": t, "weight": w} for t, w in norm_weights.items()],
            )
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

    all_warnings = analysis["warnings"] + db_warnings

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
        "disclaimer": (
            "This tool is for educational and research purposes only. "
            "It does not provide investment advice or trading recommendations."
        ),
    }
