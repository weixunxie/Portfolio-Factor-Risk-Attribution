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
    return None if s in ("", "None", "null") else s


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
        "market_cap":       _str(company.get("market_cap")),
        "pe_ratio":         _str(company.get("pe_ratio")),
        "week_52_high":     _str(company.get("week_52_high")),
        "week_52_low":      _str(company.get("week_52_low")),
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
            RETURNING id
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
    Returns the row's UUID (id) or None if accession_number is missing.

    Required key: accession_number
    """
    accession = _str(metadata.get("accession_number"))
    if not accession:
        raise ValueError("insert_sec_filing: 'accession_number' is required")

    params = {
        "ticker":               (metadata.get("ticker") or "").upper().strip() or None,
        "cik":                  _str(metadata.get("cik")),
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
            RETURNING id
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
    """Insert one analysis run and return its UUID (str)."""
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
                :request_holdings_json::jsonb,
                :start_date,
                :end_date,
                :risk_metrics_json::jsonb,
                :correlation_matrix_json::jsonb,
                :top_risk_contributors_json::jsonb,
                :stress_analysis_json::jsonb,
                :company_risk_evidence_json::jsonb,
                :warnings_json::jsonb,
                :status,
                :error_message,
                NOW()
            )
            RETURNING id
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


# ── H. api_cache_metadata ──────────────────────────────────────────────────────

def insert_api_cache_metadata(metadata: dict[str, Any]) -> None:
    """
    Insert or update a row in *api_cache_metadata* keyed on cache_key.
    """
    cache_key = _str(metadata.get("cache_key"))
    if not cache_key:
        raise ValueError("insert_api_cache_metadata: 'cache_key' is required")

    with get_db_session() as conn:
        conn.execute(text("""
            INSERT INTO api_cache_metadata (
                cache_key, source, ticker, endpoint, ttl_seconds,
                fetched_at, expires_at, cache_file_path, notes
            ) VALUES (
                :cache_key, :source, :ticker, :endpoint, :ttl_seconds,
                :fetched_at, :expires_at, :cache_file_path, :notes
            )
            ON CONFLICT (cache_key) DO UPDATE SET
                source          = EXCLUDED.source,
                ticker          = EXCLUDED.ticker,
                endpoint        = EXCLUDED.endpoint,
                ttl_seconds     = EXCLUDED.ttl_seconds,
                fetched_at      = EXCLUDED.fetched_at,
                expires_at      = EXCLUDED.expires_at,
                cache_file_path = EXCLUDED.cache_file_path,
                notes           = EXCLUDED.notes
        """), {
            "cache_key":       cache_key,
            "source":          _str(metadata.get("source")),
            "ticker":          (metadata.get("ticker") or "").upper().strip() or None,
            "endpoint":        _str(metadata.get("endpoint")),
            "ttl_seconds":     metadata.get("ttl_seconds"),
            "fetched_at":      _str(metadata.get("fetched_at")),
            "expires_at":      _str(metadata.get("expires_at")),
            "cache_file_path": _str(metadata.get("cache_file_path")),
            "notes":           _str(metadata.get("notes")),
        })

    logger.info("insert_api_cache_metadata: %s", cache_key)
