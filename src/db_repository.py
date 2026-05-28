"""
src/db_repository.py

Direct-PostgreSQL repository helpers for the Portfolio Risk backend.
All queries use SQLAlchemy text() — no ORM models, no Supabase REST client.

Design rules
------------
- Every public function raises on database errors; callers wrap in try/except.
- JSON/JSONB fields are passed as json.dumps(value) strings and cast to ::jsonb.
- Python None → SQL NULL for all nullable columns.
- Ticker values are always normalised to uppercase.
- No secrets are logged.

Schema alignment notes
----------------------
- portfolios.portfolio_id   (not 'id')
- analysis_runs.analysis_id (not 'id')
- sec_filings.filing_id     (not 'id')
- companies: market_cap / pe_ratio / week_52_high / week_52_low are NUMERIC
- api_cache_metadata: uses 'provider' (not 'source'), 'local_path' (not 'cache_file_path')
- portfolio_holdings has FK → companies(ticker): companies must be upserted first
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from sqlalchemy import text

from db import get_db_session

logger = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────────────────────

def _js(v: Any) -> str | None:
    """Serialize value to a JSON string for JSONB columns, or None for SQL NULL."""
    return None if v is None else json.dumps(v)


def _str(v: Any) -> str | None:
    """Return stripped string, or None if blank / 'None' / 'null'."""
    if v is None:
        return None
    s = str(v).strip()
    return None if s in ("", "None", "null", "N/A", "n/a", "-") else s


def _num(v: Any) -> float | None:
    """
    Safely convert a value to float for NUMERIC columns.
    Returns None for blank / non-numeric strings so PostgreSQL stores NULL.
    """
    if v is None:
        return None
    try:
        s = str(v).strip().replace(",", "")
        if s in ("", "None", "null", "N/A", "n/a", "-"):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _text_hash(text_: str) -> str:
    return hashlib.sha256(text_.encode()).hexdigest()


# ── A. companies ───────────────────────────────────────────────────────────────

def upsert_company(company: dict[str, Any]) -> None:
    """
    Upsert a row into *companies* keyed on ticker (uppercase).

    Accepted input keys (from market_data_provider profile):
        ticker, name, sector, industry, exchange, currency,
        market_cap, pe_ratio, week_52_high, week_52_low,
        description (→ business_summary), source (→ data_source)

    market_cap / pe_ratio / week_52_high / week_52_low are stored as NUMERIC —
    non-numeric strings (e.g. "N/A") are silently converted to NULL.
    """
    ticker = (company.get("ticker") or "").upper().strip()
    if not ticker:
        raise ValueError("upsert_company: 'ticker' is required")

    params = {
        "ticker":           ticker,
        "company_name":     _str(company.get("name")),
        "sector":           _str(company.get("sector")),
        "industry":         _str(company.get("industry")),
        "exchange":         _str(company.get("exchange")),
        "currency":         _str(company.get("currency")),
        "market_cap":       _num(company.get("market_cap")),
        "pe_ratio":         _num(company.get("pe_ratio")),
        "week_52_high":     _num(company.get("week_52_high")),
        "week_52_low":      _num(company.get("week_52_low")),
        "business_summary": _str(company.get("description")),
        "data_source":      _str(company.get("source")),
    }

    with get_db_session() as conn:
        conn.execute(text("""
            INSERT INTO companies (
                ticker, company_name, sector, industry, exchange, currency,
                market_cap, pe_ratio, week_52_high, week_52_low,
                business_summary, data_source, last_updated
            ) VALUES (
                :ticker, :company_name, :sector, :industry, :exchange, :currency,
                :market_cap, :pe_ratio, :week_52_high, :week_52_low,
                :business_summary, :data_source, NOW()
            )
            ON CONFLICT (ticker) DO UPDATE SET
                company_name     = EXCLUDED.company_name,
                sector           = EXCLUDED.sector,
                industry         = EXCLUDED.industry,
                exchange         = EXCLUDED.exchange,
                currency         = EXCLUDED.currency,
                market_cap       = EXCLUDED.market_cap,
                pe_ratio         = EXCLUDED.pe_ratio,
                week_52_high     = EXCLUDED.week_52_high,
                week_52_low      = EXCLUDED.week_52_low,
                business_summary = EXCLUDED.business_summary,
                data_source      = EXCLUDED.data_source,
                last_updated     = NOW()
        """), params)

    logger.info("upsert_company: %s", ticker)


# ── B. portfolios ──────────────────────────────────────────────────────────────

def create_portfolio(
    portfolio_name: str,
    description: str | None = None,
    portfolio_goal: str | None = None,
) -> str:
    """Insert a new portfolio and return its UUID (str)."""
    with get_db_session() as conn:
        row = conn.execute(text("""
            INSERT INTO portfolios (portfolio_name, description, portfolio_goal, created_at)
            VALUES (:portfolio_name, :description, :portfolio_goal, NOW())
            RETURNING portfolio_id
        """), {
            "portfolio_name": portfolio_name,
            "description":    description,
            "portfolio_goal": portfolio_goal,
        }).fetchone()

    portfolio_id = str(row[0])
    logger.info("create_portfolio: id=%s name=%s", portfolio_id, portfolio_name)
    return portfolio_id


# ── C. portfolio_holdings ──────────────────────────────────────────────────────

def upsert_portfolio_holdings(
    portfolio_id: str,
    holdings: list[dict[str, Any]],
) -> None:
    """
    Upsert portfolio holdings.
    Conflict key: (portfolio_id, ticker).
    Each item in *holdings* must have 'ticker' and 'weight'.

    NOTE: companies(ticker) must already exist before calling this function
    because portfolio_holdings has a foreign key to companies.
    Call upsert_company() for each ticker first.
    """
    if not holdings:
        return

    with get_db_session() as conn:
        for h in holdings:
            conn.execute(text("""
                INSERT INTO portfolio_holdings (portfolio_id, ticker, weight)
                VALUES (:portfolio_id, :ticker, :weight)
                ON CONFLICT (portfolio_id, ticker) DO UPDATE SET
                    weight = EXCLUDED.weight
            """), {
                "portfolio_id": portfolio_id,
                "ticker":       h["ticker"].upper().strip(),
                "weight":       float(h["weight"]),
            })

    logger.info("upsert_portfolio_holdings: portfolio=%s count=%d", portfolio_id, len(holdings))


# ── D. sec_filings ─────────────────────────────────────────────────────────────

def insert_sec_filing(metadata: dict[str, Any]) -> str | None:
    """
    Insert or update a row in *sec_filings* keyed on accession_number.
    Returns the row's UUID (filing_id) or None if accession_number is missing.

    NOTE: companies(ticker) must already exist before calling this function
    because sec_filings has a foreign key to companies.
    """
    accession = _str(metadata.get("accession_number"))
    if not accession:
        raise ValueError("insert_sec_filing: 'accession_number' is required")

    ticker = (metadata.get("ticker") or "").upper().strip() or None
    if not ticker:
        raise ValueError("insert_sec_filing: 'ticker' is required")

    # Ensure cik is not None/empty — use a placeholder if missing
    cik = _str(metadata.get("cik")) or "unknown"

    params = {
        "ticker":               ticker,
        "cik":                  cik,
        "filing_type":          _str(metadata.get("filing_type")) or "10-K",
        "filing_date":          _str(metadata.get("filing_date")),
        "accession_number":     accession,
        "source_url":           _str(metadata.get("source_url")),
        "local_path":           _str(metadata.get("local_path")),
        "risk_factors_path":    _str(metadata.get("risk_factors_path")),
        "risk_factors_extracted": bool(metadata.get("risk_factors_extracted", False)),
        "qdrant_ingested":      bool(metadata.get("qdrant_ingested", False)),
    }

    with get_db_session() as conn:
        row = conn.execute(text("""
            INSERT INTO sec_filings (
                ticker, cik, filing_type, filing_date, accession_number,
                source_url, local_path, risk_factors_path,
                risk_factors_extracted, qdrant_ingested
            ) VALUES (
                :ticker, :cik, :filing_type, :filing_date, :accession_number,
                :source_url, :local_path, :risk_factors_path,
                :risk_factors_extracted, :qdrant_ingested
            )
            ON CONFLICT (accession_number) DO UPDATE SET
                ticker                = EXCLUDED.ticker,
                cik                   = EXCLUDED.cik,
                filing_type           = EXCLUDED.filing_type,
                filing_date           = EXCLUDED.filing_date,
                source_url            = EXCLUDED.source_url,
                local_path            = EXCLUDED.local_path,
                risk_factors_path     = EXCLUDED.risk_factors_path,
                risk_factors_extracted = EXCLUDED.risk_factors_extracted,
                qdrant_ingested       = EXCLUDED.qdrant_ingested
            RETURNING filing_id
        """), params).fetchone()

    filing_id = str(row[0]) if row else None
    logger.info("insert_sec_filing: %s id=%s", accession, filing_id)
    return filing_id


# ── E. sec_filings — qdrant status ─────────────────────────────────────────────

def update_sec_filing_qdrant_status(
    accession_number: str,
    qdrant_ingested: bool,
    qdrant_error: str | None = None,
) -> None:
    """Flip the qdrant_ingested flag (and optional error) on a sec_filings row."""
    accession = accession_number.strip()
    with get_db_session() as conn:
        conn.execute(text("""
            UPDATE sec_filings
            SET qdrant_ingested = :qdrant_ingested,
                qdrant_error    = :qdrant_error
            WHERE accession_number = :accession_number
        """), {
            "accession_number": accession,
            "qdrant_ingested":  qdrant_ingested,
            "qdrant_error":     qdrant_error,
        })

    logger.info(
        "update_sec_filing_qdrant_status: %s ingested=%s", accession, qdrant_ingested
    )


# ── F. analysis_runs ───────────────────────────────────────────────────────────

def insert_analysis_run(
    request_holdings: list[dict[str, Any]],
    risk_metrics: dict[str, Any],
    correlation_matrix: dict[str, Any],
    top_risk_contributors: list[dict[str, Any]],
    stress_analysis: list[dict[str, Any]],
    company_risk_evidence: dict[str, Any],
    warnings: list[str],
    portfolio_id: str | None = None,
    status: str = "completed",
    error_message: str | None = None,
) -> str:
    """Insert one analysis run and return its UUID (analysis_id)."""
    start_date = _str(risk_metrics.get("data_start"))
    end_date   = _str(risk_metrics.get("data_end"))

    params = {
        "portfolio_id":               portfolio_id,
        "request_holdings_json":      _js(request_holdings),
        "start_date":                 start_date,
        "end_date":                   end_date,
        "risk_metrics_json":          _js(risk_metrics),
        "correlation_matrix_json":    _js(correlation_matrix),
        "top_risk_contributors_json": _js(top_risk_contributors),
        "stress_analysis_json":       _js(stress_analysis),
        "company_risk_evidence_json": _js(company_risk_evidence),
        "warnings_json":              _js(warnings),
        "status":                     status,
        "error_message":              error_message,
    }

    with get_db_session() as conn:
        row = conn.execute(text("""
            INSERT INTO analysis_runs (
                portfolio_id,
                request_holdings_json,
                start_date,
                end_date,
                risk_metrics_json,
                correlation_matrix_json,
                top_risk_contributors_json,
                stress_analysis_json,
                company_risk_evidence_json,
                warnings_json,
                status,
                error_message,
                created_at
            ) VALUES (
                :portfolio_id,
                CAST(:request_holdings_json AS jsonb),
                :start_date,
                :end_date,
                CAST(:risk_metrics_json AS jsonb),
                CAST(:correlation_matrix_json AS jsonb),
                CAST(:top_risk_contributors_json AS jsonb),
                CAST(:stress_analysis_json AS jsonb),
                CAST(:company_risk_evidence_json AS jsonb),
                CAST(:warnings_json AS jsonb),
                :status,
                :error_message,
                NOW()
            )
            RETURNING analysis_id
        """), params).fetchone()

    analysis_id = str(row[0])
    logger.info("insert_analysis_run: id=%s portfolio=%s", analysis_id, portfolio_id)
    return analysis_id


# ── G. rag_documents ───────────────────────────────────────────────────────────

def insert_rag_document(metadata: dict[str, Any]) -> None:
    """
    Insert or update one row in *rag_documents*.
    Conflict key: (qdrant_collection, chunk_id).
    """
    chunk_id   = _str(metadata.get("chunk_id"))
    collection = _str(metadata.get("qdrant_collection"))
    if not chunk_id or not collection:
        raise ValueError(
            "insert_rag_document: 'chunk_id' and 'qdrant_collection' are required"
        )

    text_val  = metadata.get("text") or ""
    text_hash = _text_hash(text_val) if text_val else None

    with get_db_session() as conn:
        conn.execute(text("""
            INSERT INTO rag_documents (
                ticker, filing_id, qdrant_collection, qdrant_point_id,
                chunk_id, source_type, source_file, filing_date,
                accession_number, source_url, text_hash,
                chunk_char_start, chunk_char_end, created_at
            ) VALUES (
                :ticker, :filing_id, :qdrant_collection, :qdrant_point_id,
                :chunk_id, :source_type, :source_file, :filing_date,
                :accession_number, :source_url, :text_hash,
                :chunk_char_start, :chunk_char_end, NOW()
            )
            ON CONFLICT (qdrant_collection, chunk_id) DO UPDATE SET
                ticker           = EXCLUDED.ticker,
                qdrant_point_id  = EXCLUDED.qdrant_point_id,
                source_type      = EXCLUDED.source_type,
                source_file      = EXCLUDED.source_file,
                filing_date      = EXCLUDED.filing_date,
                accession_number = EXCLUDED.accession_number,
                source_url       = EXCLUDED.source_url,
                text_hash        = EXCLUDED.text_hash
        """), {
            "ticker":            (metadata.get("ticker") or "").upper().strip() or None,
            "filing_id":         _str(metadata.get("filing_id")),
            "qdrant_collection": collection,
            "qdrant_point_id":   _str(metadata.get("qdrant_point_id")),
            "chunk_id":          chunk_id,
            "source_type":       _str(metadata.get("source_type")),
            "source_file":       _str(metadata.get("source_file")),
            "filing_date":       _str(metadata.get("filing_date")),
            "accession_number":  _str(metadata.get("accession_number")),
            "source_url":        _str(metadata.get("source_url")),
            "text_hash":         text_hash,
            "chunk_char_start":  metadata.get("chunk_char_start"),
            "chunk_char_end":    metadata.get("chunk_char_end"),
        })


def insert_rag_documents_bulk(records: list[dict[str, Any]]) -> int:
    """
    Upsert a batch of rag_document rows. Returns the number of rows written.
    Rows with missing chunk_id or qdrant_collection are silently skipped.
    """
    if not records:
        return 0

    rows = []
    for metadata in records:
        chunk_id   = _str(metadata.get("chunk_id"))
        collection = _str(metadata.get("qdrant_collection"))
        if not chunk_id or not collection:
            continue
        text_val  = metadata.get("text") or ""
        text_hash = _text_hash(text_val) if text_val else None
        rows.append({
            "ticker":            (metadata.get("ticker") or "").upper().strip() or None,
            "filing_id":         _str(metadata.get("filing_id")),
            "qdrant_collection": collection,
            "qdrant_point_id":   _str(metadata.get("qdrant_point_id")),
            "chunk_id":          chunk_id,
            "source_type":       _str(metadata.get("source_type")),
            "source_file":       _str(metadata.get("source_file")),
            "filing_date":       _str(metadata.get("filing_date")),
            "accession_number":  _str(metadata.get("accession_number")),
            "source_url":        _str(metadata.get("source_url")),
            "text_hash":         text_hash,
            "chunk_char_start":  metadata.get("chunk_char_start"),
            "chunk_char_end":    metadata.get("chunk_char_end"),
        })

    if rows:
        with get_db_session() as conn:
            conn.execute(text("""
                INSERT INTO rag_documents (
                    ticker, filing_id, qdrant_collection, qdrant_point_id,
                    chunk_id, source_type, source_file, filing_date,
                    accession_number, source_url, text_hash,
                    chunk_char_start, chunk_char_end, created_at
                ) VALUES (
                    :ticker, :filing_id, :qdrant_collection, :qdrant_point_id,
                    :chunk_id, :source_type, :source_file, :filing_date,
                    :accession_number, :source_url, :text_hash,
                    :chunk_char_start, :chunk_char_end, NOW()
                )
                ON CONFLICT (qdrant_collection, chunk_id) DO UPDATE SET
                    ticker           = EXCLUDED.ticker,
                    qdrant_point_id  = EXCLUDED.qdrant_point_id,
                    source_type      = EXCLUDED.source_type,
                    source_file      = EXCLUDED.source_file,
                    filing_date      = EXCLUDED.filing_date,
                    accession_number = EXCLUDED.accession_number,
                    source_url       = EXCLUDED.source_url,
                    text_hash        = EXCLUDED.text_hash
            """), rows)

    logger.info("insert_rag_documents_bulk: %d rows", len(rows))
    return len(rows)


# ── read helpers ──────────────────────────────────────────────────────────────

def get_company_from_db(ticker: str) -> "dict | None":
    """
    Read a company profile row from *companies*.
    Returns None if the ticker is not found.
    Includes 'last_updated' as a Python datetime so callers can enforce TTL.
    """
    t = ticker.upper().strip()
    with get_db_session() as conn:
        row = conn.execute(text("""
            SELECT ticker, company_name, sector, industry, exchange, currency,
                   market_cap, pe_ratio, week_52_high, week_52_low,
                   business_summary, data_source, last_updated
            FROM companies
            WHERE ticker = :ticker
        """), {"ticker": t}).fetchone()

    if row is None:
        return None

    return {
        "ticker":       row[0],
        "name":         row[1] or "",
        "sector":       row[2] or "",
        "industry":     row[3] or "",
        "exchange":     row[4] or "",
        "currency":     row[5] or "",
        "market_cap":   str(row[6]) if row[6] is not None else "",
        "pe_ratio":     str(row[7]) if row[7] is not None else "",
        "week_52_high": str(row[8]) if row[8] is not None else "",
        "week_52_low":  str(row[9]) if row[9] is not None else "",
        "description":  row[10] or "",
        "source":       row[11] or "database",
        "last_updated": row[12],   # datetime | None — caller checks TTL
    }


def get_sec_filing_from_db(ticker: str, filing_type: str = "10-K") -> "dict | None":
    """
    Return the most-recent *sec_filings* row where risk_factors_extracted=TRUE.
    Returns None if not found or DB is unavailable.
    """
    t = ticker.upper().strip()
    with get_db_session() as conn:
        row = conn.execute(text("""
            SELECT accession_number, filing_date, source_url,
                   risk_factors_path, qdrant_ingested, cik
            FROM sec_filings
            WHERE ticker       = :ticker
              AND filing_type  = :filing_type
              AND risk_factors_extracted = TRUE
            ORDER BY filing_date DESC NULLS LAST
            LIMIT 1
        """), {"ticker": t, "filing_type": filing_type}).fetchone()

    if row is None:
        return None

    return {
        "accession_number": row[0],
        "filing_date":      str(row[1]) if row[1] else None,
        "source_url":       row[2],
        "risk_factors_path": row[3],
        "qdrant_ingested":  bool(row[4]),
        "cik":              row[5],
    }


# ── H. api_cache_metadata ──────────────────────────────────────────────────────

def insert_api_cache_metadata(metadata: dict[str, Any]) -> None:
    """
    Insert or update a row in *api_cache_metadata* keyed on cache_key.

    Schema columns: cache_key, provider (NOT NULL), endpoint, ticker,
                    local_path, fetched_at, expires_at, status, error_message.
    """
    cache_key = _str(metadata.get("cache_key"))
    if not cache_key:
        raise ValueError("insert_api_cache_metadata: 'cache_key' is required")

    # 'source' and 'provider' are both accepted as the provider name
    provider = _str(metadata.get("provider") or metadata.get("source")) or "unknown"

    with get_db_session() as conn:
        conn.execute(text("""
            INSERT INTO api_cache_metadata (
                cache_key, provider, ticker, endpoint,
                fetched_at, expires_at, local_path
            ) VALUES (
                :cache_key, :provider, :ticker, :endpoint,
                :fetched_at, :expires_at, :local_path
            )
            ON CONFLICT (cache_key) DO UPDATE SET
                provider    = EXCLUDED.provider,
                ticker      = EXCLUDED.ticker,
                endpoint    = EXCLUDED.endpoint,
                fetched_at  = EXCLUDED.fetched_at,
                expires_at  = EXCLUDED.expires_at,
                local_path  = EXCLUDED.local_path
        """), {
            "cache_key":  cache_key,
            "provider":   provider,
            "ticker":     (metadata.get("ticker") or "").upper().strip() or None,
            "endpoint":   _str(metadata.get("endpoint")),
            "fetched_at": _str(metadata.get("fetched_at")),
            "expires_at": _str(metadata.get("expires_at")),
            "local_path": _str(metadata.get("cache_file_path") or metadata.get("local_path")),
        })

    logger.info("insert_api_cache_metadata: %s", cache_key)
