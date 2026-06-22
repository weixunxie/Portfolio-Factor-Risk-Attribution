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

# ── optional Postgres layer ────────────────────────────────────────────────────
try:
    import db as _db
    import db_repository as _repo
    _DB_IMPORT_OK = True
except ImportError:
    _DB_IMPORT_OK = False


def _db_live() -> bool:
    return _DB_IMPORT_OK and _db.is_configured()
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

# Section start/end markers, matched against whole (stripped) lines so that
# in-text cross-references (a sentence mentioning "Risk Factors") never match --
# only standalone headings do. Two start forms are needed because issuers label
# the section differently:
#   - standard:           "ITEM 1A." / "Item 1A. Risk Factors"
#   - thematic (INTC/MS): a bare "Risk Factors" heading (no "Item 1A" string)
_RE_START = re.compile(r"^(?:item\s+1a\b.*|risk factors\.?)\s*$", re.IGNORECASE)
# End at the next section heading -- by item number, or by title for layouts
# that print the title without the item number on the same line.
_RE_END = re.compile(
    r"^(?:item\s+(?:1b|1c|2)\b.*|unresolved staff comments.*|properties|cybersecurity)\s*$",
    re.IGNORECASE,
)

# A real Item 1A section is far longer than this. Anything shorter is a TOC
# entry, a cross-reference, or an "incorporated by reference" stub (some
# financial issuers, e.g. WFC, carry no risk factors in the 10-K body itself).
_MIN_SECTION_CHARS = 1_000


def _extract_risk_factors(html: str) -> "str | None":
    """
    Parse 10-K HTML and return the Item 1A Risk Factors section as plain text.

    Splits into lines, finds every standalone section heading, and keeps the
    longest span from a start heading ("Item 1A" or a bare "Risk Factors") to
    the next end heading ("Item 1B/1C/2", "Unresolved Staff Comments",
    "Cybersecurity", "Properties"). The real section dwarfs every TOC entry, so
    the longest span is the section -- robust across standard, iXBRL, and
    thematic-heading layouts that defeat per-line "Item 1A" matching.

    Returns None when no usable section is found (e.g. risk factors are
    incorporated by reference and absent from the 10-K body).
    """
    soup = BeautifulSoup(html, "lxml")

    # Strip noise
    for tag in soup.find_all(["script", "style", "svg"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    # Normalise unicode whitespace that otherwise breaks heading matches
    text = text.replace("\xa0", " ").replace("​", "").replace(" ", " ")
    lines = [l.strip() for l in text.split("\n")]

    starts = [i for i, l in enumerate(lines) if _RE_START.match(l)]
    ends = [i for i, l in enumerate(lines) if _RE_END.match(l)]
    if not starts:
        return None

    # For each start heading take the next end heading (or a bounded fallback),
    # and keep the longest resulting span -- that is the real section, not a TOC
    # row whose own end heading is only a line or two away.
    best_start, best_end, best_chars = 0, 0, 0
    for s in starts:
        following = [e for e in ends if e > s]
        e = following[0] if following else min(s + 3000, len(lines))
        chars = sum(len(lines[k]) + 1 for k in range(s, e))
        if chars > best_chars:
            best_start, best_end, best_chars = s, e, chars

    if best_chars < _MIN_SECTION_CHARS:
        return None

    # Tidy whitespace: drop blanks, collapse repeated short lines (page
    # separators, repeated running headers).
    cleaned: list[str] = []
    for l in lines[best_start:best_end]:
        if not l:
            continue
        if cleaned and l == cleaned[-1] and len(l) < 20:
            continue
        cleaned.append(l)

    text_out = "\n\n".join(cleaned)

    # Cap at ~12 000 words to keep markdown files manageable
    words = text_out.split()
    if len(words) > 12_000:
        text_out = (
            " ".join(words[:12_000])
            + "\n\n*[Truncated -- showing first 12 000 words of Item 1A Risk Factors.]*"
        )

    return text_out if text_out.strip() else None


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
        # ── Priority 0: Postgres ──────────────────────────────────────────────
        # If we have a DB record with risk_factors_extracted=True AND the local
        # markdown file still exists, serve it without hitting SEC EDGAR.
        if _db_live():
            try:
                db_filing = _repo.get_sec_filing_from_db(t)
                if db_filing and db_filing.get("risk_factors_path"):
                    local_file = Path(db_filing["risk_factors_path"])
                    if local_file.exists():
                        print(f"[SEC] Using DB-cached filing for {t}: {local_file}")
                        text_content = local_file.read_text(encoding="utf-8")
                        # Strip frontmatter to get the raw extracted text
                        body = text_content
                        if text_content.startswith("---"):
                            end = text_content.find("---", 3)
                            if end != -1:
                                body = text_content[end + 3:].strip()
                        return {
                            "success":          True,
                            "ticker":           t,
                            "cik":              db_filing.get("cik"),
                            "filing_date":      db_filing.get("filing_date"),
                            "accession_number": db_filing.get("accession_number"),
                            "source_url":       db_filing.get("source_url"),
                            "preview":          body[:500],
                            "path":             str(local_file),
                            "output_path":      str(local_file),
                            "cached":           True,
                            "error":            None,
                        }
            except Exception as exc:
                print(f"[SEC] DB check failed for {t}: {exc}")

        # ── Priority 1: local JSON cache ──────────────────────────────────────
        cached = get_cache(cache_key, ttl_seconds=_EXTRACTED_CACHE_TTL)
        if cached is not None:
            return {**cached, "cached": True}

    # ── 3. Get filing metadata from SEC EDGAR ────────────────────────────────
    meta_result = get_latest_10k_metadata(t)
    if not meta_result["success"]:
        return _failure(t, None, None, None, None, meta_result["error"])

    meta = meta_result["data"]
    filing = meta["latest_10k"]
    cik = meta["cik"]
    doc_url = filing["document_url"]
    filing_date = filing["filing_date"]
    accession = filing["accession_number"]

    # ── 4. Download filing HTML ───────────────────────────────────────────────
    html = _download_filing_html(doc_url, t)
    if not html:
        return _failure(t, cik, filing_date, accession, doc_url,
                        "Failed to download the 10-K filing from SEC EDGAR")

    # ── 5. Extract Risk Factors section ──────────────────────────────────────
    print(f"[SEC] Extracting Item 1A for {t} ...")
    extracted = _extract_risk_factors(html)
    if not extracted:
        return _failure(t, cik, filing_date, accession, doc_url,
                        "Could not locate the Item 1A Risk Factors section in the filing")

    # ── 6. Write markdown document ───────────────────────────────────────────
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
        "success":          True,
        "ticker":           t,
        "cik":              cik,
        "filing_date":      filing_date,
        "accession_number": accession,
        "source_url":       doc_url,
        "preview":          extracted[:500],
        "path":             str(out_path),
        "output_path":      str(out_path),
        "error":            None,
    }

    # ── Write-back: local JSON cache ──────────────────────────────────────────
    set_cache(cache_key, {k: v for k, v in result.items()})

    # ── Write-back: Postgres ──────────────────────────────────────────────────
    if _db_live():
        try:
            _repo.insert_sec_filing({
                "ticker":               t,
                "cik":                  str(cik) if cik else None,
                "filing_type":          "10-K",
                "filing_date":          filing_date,
                "accession_number":     accession,
                "source_url":           doc_url,
                "risk_factors_path":    str(out_path),
                "risk_factors_extracted": True,
                "qdrant_ingested":      False,
            })
        except Exception as exc:
            print(f"[SEC] DB write-back failed for {t}: {exc}")

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
