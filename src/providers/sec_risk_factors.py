"""
SEC EDGAR 10-K Risk Factors extraction.

Downloads the latest 10-K filing for a given ticker from SEC EDGAR,
extracts the Item 1A Risk Factors section, and saves it as markdown under:
  data/documents/{TICKER}/10k_risk_factors.md

The raw filing HTML is cached under:
  data/cache/sec_filings/{TICKER}/10k_raw.htm

Environment variables
---------------------
SEC_USER_AGENT  Required. Format: "AppName YourEmail@example.com"

Usage
-----
python src/providers/sec_risk_factors.py AAPL
python src/providers/sec_risk_factors.py AAPL --force   # skip cache
"""

import os
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# ── path setup so this module can be imported OR run directly ──────────────────
_SRC = Path(__file__).parent.parent          # .../src/
_PROJECT_ROOT = _SRC.parent                  # project root
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from providers.sec_edgar_provider import get_latest_10k_metadata
from providers.cache import get_cache, set_cache
# ──────────────────────────────────────────────────────────────────────────────

DOCUMENTS_DIR = _PROJECT_ROOT / "data" / "documents"
FILINGS_CACHE_DIR = _PROJECT_ROOT / "data" / "cache" / "sec_filings"

_FILING_CACHE_TTL = 30 * 86_400     # 30 days — raw HTML rarely changes
_EXTRACTED_CACHE_TTL = 30 * 86_400  # 30 days — extracted text
_MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024  # 15 MB — enough to reach Item 1A in most 10-Ks
_REQUEST_TIMEOUT = 90               # seconds


def _sec_headers() -> dict[str, str]:
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if not ua:
        raise EnvironmentError(
            "SEC_USER_AGENT is not set. "
            "Add SEC_USER_AGENT='AppName your@email.com' to your .env file."
        )
    return {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}


def _download_filing_html(url: str, ticker: str) -> "str | None":
    """
    Stream-download the 10-K filing HTML up to _MAX_DOWNLOAD_BYTES.
    Results are cached in data/cache/sec_filings/{TICKER}/10k_raw.htm.
    """
    cache_dir = FILINGS_CACHE_DIR / ticker.upper()
    cache_file = cache_dir / "10k_raw.htm"

    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < _FILING_CACHE_TTL:
            print(f"[SEC] Using cached filing HTML for {ticker}")
            return cache_file.read_text(encoding="utf-8", errors="replace")

    print(f"[SEC] Downloading 10-K filing for {ticker} from SEC EDGAR ...")
    print(f"[SEC]   {url}")

    try:
        headers = _sec_headers()
    except EnvironmentError as exc:
        print(f"[SEC] {exc}")
        return None

    try:
        with requests.get(
            url, headers=headers, stream=True, timeout=_REQUEST_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_content(chunk_size=65_536):
                if chunk:
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= _MAX_DOWNLOAD_BYTES:
                        print(
                            f"[SEC]   Reached {_MAX_DOWNLOAD_BYTES // 1_048_576} MB "
                            "limit — stopping download."
                        )
                        break
            html = b"".join(chunks).decode("utf-8", errors="replace")
            print(f"[SEC]   Downloaded {total / 1024:.0f} KB")
    except requests.RequestException as exc:
        print(f"[SEC] Download error: {exc}")
        return None

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(html, encoding="utf-8")
    return html


# ── Risk Factors section extraction ───────────────────────────────────────────

# Heading patterns — must match a short standalone line (not a sentence)
_RE_1A_HEADING = re.compile(
    r"^(?:ITEM|Item)\s+1A\.?\s*(?:RISK\s+FACTORS|Risk\s+Factors)?\.?\s*$",
    re.IGNORECASE,
)
_RE_1A_LOOSE = re.compile(
    r"1\s*A",
    re.IGNORECASE,
)
_RE_END = re.compile(
    r"^(?:ITEM|Item)\s+(?:1B|2)[\.\s]",
    re.IGNORECASE,
)


def _extract_risk_factors(html: str) -> "str | None":
    """
    Parse 10-K HTML and return the Item 1A Risk Factors section as plain text.

    Handles old-style HTML and iXBRL documents.
    Returns None if the section cannot be located.
    """
    soup = BeautifulSoup(html, "lxml")

    # Strip noise
    for tag in soup.find_all(["script", "style", "svg"]):
        tag.decompose()

    raw = soup.get_text(separator="\n")

    # Normalise to non-blank lines
    lines = [l.strip() for l in raw.split("\n")]
    lines = [l for l in lines if l]

    # ── find start index ──────────────────────────────────────────────────────
    # Strategy: strict heading match first, then looser match.
    # Avoid TOC entries: the TOC line is typically very short, and the real
    # section heading is followed by paragraph text (lines ≥ 40 chars).

    def _has_content_after(idx: int, min_substantial: int = 3) -> bool:
        window = lines[idx + 1: idx + 20]
        return sum(1 for l in window if len(l) >= 40) >= min_substantial

    start_idx: "int | None" = None

    # Pass 1: strict heading regex
    for i, l in enumerate(lines):
        if _RE_1A_HEADING.match(l) and _has_content_after(i):
            start_idx = i
            break

    # Pass 2: looser search (e.g. "ITEM 1A. RISK FACTORS" with extra spaces)
    if start_idx is None:
        for i, l in enumerate(lines):
            if (
                len(l) < 80
                and _RE_1A_LOOSE.search(l)
                and re.search(r"RISK", l, re.I)
                and _has_content_after(i)
            ):
                start_idx = i
                break

    if start_idx is None:
        return None

    # ── find end index ────────────────────────────────────────────────────────
    end_idx: "int | None" = None
    for i in range(start_idx + 1, min(start_idx + 5000, len(lines))):
        if _RE_END.match(lines[i]) and len(lines[i]) < 80:
            end_idx = i
            break

    end = end_idx if end_idx else min(start_idx + 3000, len(lines))
    section_lines = lines[start_idx:end]

    # Collapse runs of identical short lines (e.g. repeated page separators)
    cleaned: list[str] = []
    for l in section_lines:
        if cleaned and l == cleaned[-1] and len(l) < 20:
            continue
        cleaned.append(l)

    text = "\n\n".join(cleaned)

    # Cap at ~12 000 words to keep markdown files manageable
    words = text.split()
    if len(words) > 12_000:
        text = (
            " ".join(words[:12_000])
            + "\n\n*[Truncated — showing first 12 000 words of Item 1A Risk Factors.]*"
        )

    return text if text.strip() else None


# ── public API ─────────────────────────────────────────────────────────────────

def extract_risk_factors(ticker: str, force: bool = False) -> dict:
    """
    Extract the Item 1A Risk Factors section from the latest 10-K for *ticker*.

    Returns
    -------
    {
      "success": bool,
      "ticker": str,
      "cik": int | None,
      "filing_date": str | None,
      "accession_number": str | None,
      "source_url": str | None,
      "preview": str | None,       # first 500 chars of extracted text
      "output_path": str | None,   # absolute path to the saved markdown file
      "cached": bool,
      "error": str | None,
    }
    """
    t = ticker.upper().strip()
    cache_key = f"sec_extracted_{t}"

    if not force:
        cached = get_cache(cache_key, ttl_seconds=_EXTRACTED_CACHE_TTL)
        if cached is not None:
            return {**cached, "cached": True}

    # ── 1. Get filing metadata ─────────────────────────────────────────────────
    meta_result = get_latest_10k_metadata(t)
    if not meta_result["success"]:
        return _failure(t, None, None, None, None, meta_result["error"])

    meta = meta_result["data"]
    filing = meta["latest_10k"]
    cik = meta["cik"]
    doc_url = filing["document_url"]
    filing_date = filing["filing_date"]
    accession = filing["accession_number"]

    # ── 2. Download filing HTML ────────────────────────────────────────────────
    html = _download_filing_html(doc_url, t)
    if not html:
        return _failure(t, cik, filing_date, accession, doc_url,
                        "Failed to download the 10-K filing from SEC EDGAR")

    # ── 3. Extract Risk Factors section ───────────────────────────────────────
    print(f"[SEC] Extracting Item 1A for {t} ...")
    extracted = _extract_risk_factors(html)
    if not extracted:
        return _failure(t, cik, filing_date, accession, doc_url,
                        "Could not locate the Item 1A Risk Factors section in the filing")

    # ── 4. Write markdown document ────────────────────────────────────────────
    out_dir = DOCUMENTS_DIR / t
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "10k_risk_factors.md"

    markdown = (
        f"---\n"
        f"ticker: {t}\n"
        f"cik: {cik}\n"
        f"filing_type: 10-K\n"
        f"filing_date: {filing_date}\n"
        f"accession_number: {accession}\n"
        f"source_url: {doc_url}\n"
        f"---\n\n"
        f"# {t} — 10-K Risk Factors (Item 1A)\n\n"
        + extracted
    )
    out_path.write_text(markdown, encoding="utf-8")
    print(f"[SEC] Saved → {out_path}")

    result: dict = {
        "success": True,
        "ticker": t,
        "cik": cik,
        "filing_date": filing_date,
        "accession_number": accession,
        "source_url": doc_url,
        "preview": extracted[:500],
        "output_path": str(out_path),
        "error": None,
    }
    set_cache(cache_key, {k: v for k, v in result.items()})
    return {**result, "cached": False}


def _failure(
    ticker: str,
    cik: "int | None",
    filing_date: "str | None",
    accession: "str | None",
    source_url: "str | None",
    error: str,
) -> dict:
    return {
        "success": False,
        "ticker": ticker,
        "cik": cik,
        "filing_date": filing_date,
        "accession_number": accession,
        "source_url": source_url,
        "preview": None,
        "output_path": None,
        "cached": False,
        "error": error,
    }


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ticker_arg = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    force_arg = "--force" in sys.argv

    result = extract_risk_factors(ticker_arg, force=force_arg)

    if result["success"]:
        print(f"\n[OK] Filing date  : {result['filing_date']}")
        print(f"[OK] Accession    : {result['accession_number']}")
        print(f"[OK] Saved to     : {result['output_path']}")
        print(f"[OK] Cached       : {result['cached']}")
        print(f"\n--- Preview (first 500 chars) ---")
        print(result["preview"])
    else:
        print(f"\n[ERROR] {result['error']}")
        sys.exit(1)
