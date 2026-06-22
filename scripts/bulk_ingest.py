"""
Bulk pre-ingest SEC 10-K risk factors for a universe of tickers.

Drives the *deployed* backend over HTTP — the embedding work runs on Railway
(which has a working sentence-transformers), so this script needs no heavy
local deps, just `requests`. Results land in Qdrant (durable), so each ticker
only needs to be ingested once, ever.

For each ticker:
  1. Skip if it already has evidence in Qdrant (idempotent, cheap check).
  2. GET  /sec-risk-factors/{t}     — extract Item 1A from the latest 10-K.
  3. POST /ingest-risk-factors/{t}  — chunk, embed, upsert into Qdrant.

Usage:
  python scripts/bulk_ingest.py                         # whole data/universe.txt
  python scripts/bulk_ingest.py --limit 5               # first 5 only (smoke test)
  python scripts/bulk_ingest.py --only AMD NKE MU       # specific tickers
  python scripts/bulk_ingest.py --base https://host     # override backend URL
  python scripts/bulk_ingest.py --throttle 3            # seconds between tickers
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_UNIVERSE = ROOT / "data" / "universe.txt"
DEFAULT_BASE = "https://web-production-48e28.up.railway.app"
_QUERY = "key business risks revenue concentration regulatory competition"


def load_universe(path: Path) -> list[str]:
    out: list[str] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line.upper())
    return out


def already_ingested(base: str, ticker: str, timeout: int) -> bool:
    """Cheap check: does Qdrant already return any chunk for this ticker?"""
    try:
        r = requests.get(
            f"{base}/company-risk-query",
            params={"ticker": ticker, "query": _QUERY, "top_k": 1},
            timeout=timeout,
        )
        if r.status_code == 200:
            results = r.json().get("results")
            return isinstance(results, list) and len(results) > 0
    except requests.RequestException:
        pass
    return False


def ingest_one(base: str, ticker: str, timeout: int) -> tuple[str, str]:
    """Returns (status, detail). status in {ok, skipped, extract_failed, ingest_failed, error}."""
    try:
        # force=true re-downloads and rewrites the markdown file. The backend's
        # filesystem is ephemeral, so a cached extract may have no file on disk
        # for the ingest step to read — forcing guarantees the file exists.
        ex = requests.get(
            f"{base}/sec-risk-factors/{ticker}",
            params={"force": "true"},
            timeout=timeout,
        )
        if ex.status_code != 200:
            return "extract_failed", f"HTTP {ex.status_code}: {ex.text[:120]}"
        if not ex.json().get("success"):
            return "extract_failed", str(ex.json().get("error"))[:120]

        ing = requests.post(f"{base}/ingest-risk-factors/{ticker}", timeout=timeout)
        if ing.status_code != 200:
            return "ingest_failed", f"HTTP {ing.status_code}: {ing.text[:120]}"
        body = ing.json()
        if not body.get("success"):
            return "ingest_failed", str(body.get("error"))[:120]
        return "ok", f"{body.get('chunks_ingested', 0)} chunks"
    except requests.RequestException as exc:
        return "error", str(exc)[:120]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    ap.add_argument("--only", nargs="*", help="ingest just these tickers")
    ap.add_argument("--limit", type=int, default=0, help="only the first N tickers")
    ap.add_argument("--throttle", type=float, default=2.0, help="seconds between tickers")
    ap.add_argument("--timeout", type=int, default=180, help="per-request timeout (s)")
    ap.add_argument("--force", action="store_true",
                    help="re-ingest even if the ticker already has evidence")
    args = ap.parse_args()

    tickers = [t.upper() for t in args.only] if args.only else load_universe(args.universe)
    if args.limit:
        tickers = tickers[: args.limit]

    print(f"Backend: {args.base}")
    print(f"Universe: {len(tickers)} tickers\n")

    counts = {"ok": 0, "skipped": 0, "extract_failed": 0, "ingest_failed": 0, "error": 0}
    failures: list[str] = []

    for i, t in enumerate(tickers, 1):
        prefix = f"[{i}/{len(tickers)}] {t:<6}"
        if not args.force and already_ingested(args.base, t, args.timeout):
            counts["skipped"] += 1
            print(f"{prefix} skipped (already has evidence)")
            continue

        status, detail = ingest_one(args.base, t, args.timeout)
        counts[status] += 1
        print(f"{prefix} {status:<14} {detail}")
        if status not in ("ok", "skipped"):
            failures.append(f"{t}: {status} — {detail}")

        if i < len(tickers):
            time.sleep(args.throttle)

    print("\n── Summary ──")
    for k, v in counts.items():
        print(f"  {k:<14} {v}")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
