"""
Local verification for the durable provider_cache tier.

Reads DATABASE_URL from .env (never prints the value), then exercises the
two-tier cache end to end against the real Supabase table:

  1. cache_db.available()  -> should be True (table reachable)
  2. set_cache(...)        -> writes to file + Postgres
  3. raw SELECT            -> confirms the row landed in provider_cache
  4. get_cache(...)        -> reads it back and checks the value round-trips
  5. clear_cache(...)      -> cleans up the test key from both tiers

Run:  python scripts/verify_provider_cache.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


def _load_env() -> None:
    """Minimal .env loader so we don't depend on python-dotenv being installed."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def main() -> int:
    _load_env()

    if not os.environ.get("DATABASE_URL", "").strip():
        print("FAIL: DATABASE_URL is not set (create a .env with DATABASE_URL=...)")
        return 1

    from providers import cache, cache_db

    # 1. availability probe
    if not cache_db.available():
        print("FAIL: cache_db.available() is False — table unreachable or DB down")
        return 1
    print("OK  : provider_cache table reachable (persistence enabled)")

    test_key = "verify_provider_cache_probe"
    test_val = {"hello": "world", "n": 42, "list": [1, 2, 3]}

    # 2. write
    cache.set_cache(test_key, test_val)
    print("OK  : set_cache wrote to file + Postgres")

    # 3. raw confirm the row exists in Postgres
    import db as _db
    from sqlalchemy import text

    with _db.get_db_session() as conn:
        row = conn.execute(
            text("SELECT cache_key, fetched_at FROM provider_cache WHERE cache_key = :k"),
            {"k": test_key},
        ).fetchone()
    if row is None:
        print("FAIL: row not found in provider_cache after set_cache")
        return 1
    print(f"OK  : row present in Postgres (fetched_at={row[1]})")

    # 4. read back from the DB tier (delete the local file first so we know the
    #    value came from Postgres, not the file fallback)
    file_path = cache._cache_path(test_key)
    if file_path.exists():
        file_path.unlink()
    got = cache.get_cache(test_key)
    if got != test_val:
        print(f"FAIL: round-trip mismatch. got={got!r}")
        return 1
    print("OK  : get_cache read the value back from Postgres (file deleted first)")

    # 5. cleanup
    cache.clear_cache(test_key)
    with _db.get_db_session() as conn:
        still = conn.execute(
            text("SELECT 1 FROM provider_cache WHERE cache_key = :k"),
            {"k": test_key},
        ).fetchone()
    if still is not None:
        print("WARN: test key still present after clear_cache")
    else:
        print("OK  : clear_cache removed the test key from Postgres")

    print("\nALL CHECKS PASSED ✓  durable provider_cache is working.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
