"""
SEC EDGAR public data provider.

Uses only SEC's free, public APIs — no API key required, but the SEC requires
a descriptive User-Agent header on every request.

Environment variables
---------------------
SEC_USER_AGENT  Required. Format: "AppName YourEmail@example.com"
                e.g. "PortfolioRiskResearch yourname@gmail.com"
                SEC rejects requests with generic or missing User-Agents.
"""

import os
from typing import Any

import requests
from dotenv import load_dotenv

from .cache import get_cache, set_cache

load_dotenv()

# ── constants ──────────────────────────────────────────────────────────────────
_SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_TICKER_MAP_TTL = 7 * 86_400   # 7 days — ticker→CIK mapping is very stable
_SUBMISSIONS_TTL = 7 * 86_400  # 7 days — 10-K filings don't change often
_REQUEST_TIMEOUT = 15
# ──────────────────────────────────────────────────────────────────────────────


def _user_agent() -> str:
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if not ua:
        # SEC will reject requests without a proper User-Agent.
        # Users should set SEC_USER_AGENT in their .env file.
        raise EnvironmentError(
            "SEC_USER_AGENT is not set. "
            "Add SEC_USER_AGENT='AppName your@email.com' to your .env file."
        )
    return ua


def _headers() -> dict[str, str]:
    return {
        "User-Agent": _user_agent(),
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json",
    }


def _ok(data: Any, *, cached: bool = False) -> dict:
    return {"success": True, "data": data, "error": None, "cached": cached}


def _err(error: str) -> dict:
    return {"success": False, "data": None, "error": error, "cached": False}


def get_company_ticker_mapping() -> dict:
    """
    Fetch and cache the full SEC EDGAR ticker → CIK mapping.

    Returns
    -------
    {"success": bool, "data": {TICKER: {"cik": int, "title": str}}, "cached": bool}
    """
    cache_key = "sec_ticker_mapping"
    cached = get_cache(cache_key, ttl_seconds=_TICKER_MAP_TTL)
    if cached is not None:
        return _ok(cached, cached=True)

    try:
        headers = _headers()
    except EnvironmentError as exc:
        return _err(str(exc))

    try:
        resp = requests.get(_SEC_TICKERS_URL, headers=headers, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        raw = resp.json()
    except requests.RequestException as exc:
        return _err(f"network_error: {exc}")

    # Normalise to {TICKER: {cik, title}}
    mapping: dict[str, dict] = {}
    for entry in raw.values():
        ticker = entry["ticker"].upper()
        mapping[ticker] = {"cik": entry["cik_str"], "title": entry["title"]}

    set_cache(cache_key, mapping)
    return _ok(mapping)


def get_cik_for_ticker(ticker: str) -> dict:
    """
    Look up the SEC CIK number for a given ticker symbol.

    Returns
    -------
    {"success": bool, "ticker": str, "cik": int|None, "title": str|None, "error": str|None}
    """
    t = ticker.upper().strip()
    result = get_company_ticker_mapping()
    if not result["success"]:
        return {"success": False, "ticker": t, "cik": None, "title": None, "error": result["error"]}

    mapping = result["data"]
    if t not in mapping:
        return {
            "success": False,
            "ticker": t,
            "cik": None,
            "title": None,
            "error": f"Ticker '{t}' not found in SEC EDGAR company registry",
        }

    entry = mapping[t]
    return {"success": True, "ticker": t, "cik": entry["cik"], "title": entry["title"], "error": None}


def get_latest_10k_metadata(ticker: str) -> dict:
    """
    Fetch metadata for the most recent 10-K filing for a given ticker.

    Does NOT download the full filing text — only returns identifiers and URLs.

    Returns
    -------
    {
      "success": bool,
      "data": {
        "ticker": str,
        "cik": int,
        "company_name": str,
        "latest_10k": {
          "form": "10-K",
          "filing_date": "YYYY-MM-DD",
          "accession_number": "...",
          "primary_document": "...",
          "document_url": "https://www.sec.gov/...",
          "viewer_url": "https://www.sec.gov/...",
        }
      },
      "cached": bool
    }
    """
    t = ticker.upper().strip()
    cache_key = f"sec_10k_{t}"

    cached = get_cache(cache_key, ttl_seconds=_SUBMISSIONS_TTL)
    if cached is not None:
        return _ok(cached, cached=True)

    cik_result = get_cik_for_ticker(t)
    if not cik_result["success"]:
        return _err(cik_result["error"])

    cik: int = cik_result["cik"]
    padded_cik = str(cik).zfill(10)
    submissions_url = _SEC_SUBMISSIONS_URL.format(cik=padded_cik)

    try:
        headers = _headers()
    except EnvironmentError as exc:
        return _err(str(exc))

    try:
        resp = requests.get(submissions_url, headers=headers, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        submissions = resp.json()
    except requests.RequestException as exc:
        return _err(f"network_error: {exc}")

    filings = submissions.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    dates = filings.get("filingDate", [])
    accessions = filings.get("accessionNumber", [])
    primary_docs = filings.get("primaryDocument", [])

    latest_10k: dict | None = None
    for form, date, acc, doc in zip(forms, dates, accessions, primary_docs):
        if form == "10-K":
            acc_clean = acc.replace("-", "")
            latest_10k = {
                "form": form,
                "filing_date": date,
                "accession_number": acc,
                "primary_document": doc,
                "document_url": (
                    f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}/{doc}"
                ),
                "viewer_url": (
                    f"https://www.sec.gov/cgi-bin/browse-edgar"
                    f"?action=getcompany&CIK={cik}&type=10-K&dateb=&owner=include&count=10"
                ),
            }
            break  # SEC returns filings newest-first; stop at the first 10-K

    if latest_10k is None:
        return _err(f"No 10-K filings found in SEC EDGAR for ticker '{t}'")

    result_data = {
        "ticker": t,
        "cik": cik,
        "company_name": submissions.get("name", ""),
        "latest_10k": latest_10k,
    }
    set_cache(cache_key, result_data)
    return _ok(result_data)
