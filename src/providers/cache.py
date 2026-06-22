"""
Two-tier cache for provider responses.

Tier 1 (durable): a Postgres provider_cache table (see cache_db.py). Survives
                  restarts/redeploys on ephemeral hosts like Railway.
Tier 2 (local):   files under data/cache/ at the project root. Always used for
                  reads and writes; on ephemeral hosts it is a per-container
                  scratch tier, locally it is the primary store.

Reads check Postgres first, then fall back to the file. Writes go to both.
JSON is used for structured data; TXT/MD for filing text.
Cache keys are sanitised to safe filenames before use.
"""

import json
import re
import time
from pathlib import Path

from . import cache_db

# ── paths ──────────────────────────────────────────────────────────────────────
# Walk up: src/providers/ → src/ → project root
_PROJECT_ROOT = Path(__file__).parent.parent.parent
CACHE_DIR = _PROJECT_ROOT / "data" / "cache"
# ──────────────────────────────────────────────────────────────────────────────


def _safe_key(key: str) -> str:
    """Replace any character that is unsafe in a filename with an underscore."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", key)


def _cache_path(key: str, fmt: str = "json") -> Path:
    ext = "json" if fmt == "json" else "txt"
    return CACHE_DIR / f"{_safe_key(key)}.{ext}"


def _file_fresh(key: str, ttl_seconds: int, fmt: str = "json") -> bool:
    """Return True if a fresh file-cache entry exists for *key* within TTL."""
    path = _cache_path(key, fmt)
    if not path.exists():
        return False
    age_seconds = time.time() - path.stat().st_mtime
    return age_seconds < ttl_seconds


def cache_exists(key: str, ttl_seconds: int = 86400, fmt: str = "json") -> bool:
    """Return True if a fresh cache entry exists for *key* (either tier)."""
    if cache_db.db_get(key, ttl_seconds, fmt) is not None:
        return True
    return _file_fresh(key, ttl_seconds, fmt)


def get_cache(
    key: str,
    ttl_seconds: int = 86400,
    fmt: str = "json",
) -> "dict | str | None":
    """
    Return cached data for *key* if it exists and is within TTL, else None.

    Checks the durable Postgres tier first, then the local file tier.

    Parameters
    ----------
    key         : cache key string (will be sanitised)
    ttl_seconds : maximum age in seconds before cache is considered stale
    fmt         : "json" returns a dict/list; "txt" returns a raw string
    """
    # Tier 1: durable Postgres cache.
    db_val = cache_db.db_get(key, ttl_seconds, fmt)
    if db_val is not None:
        return db_val

    # Tier 2: local file cache.
    if not _file_fresh(key, ttl_seconds, fmt):
        return None
    path = _cache_path(key, fmt)
    text = path.read_text(encoding="utf-8")
    if fmt == "json":
        return json.loads(text)
    return text


def set_cache(key: str, data: "dict | list | str", fmt: str = "json") -> None:
    """
    Write *data* to both cache tiers under *key*.

    The file write always happens; the Postgres write is a no-op when the
    durable tier is unavailable.

    Parameters
    ----------
    key  : cache key string (will be sanitised)
    data : dict/list for JSON format, str for txt format
    fmt  : "json" or "txt"
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(key, fmt)
    if fmt == "json":
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        path.write_text(str(data), encoding="utf-8")

    # Mirror into the durable tier (no-op if Postgres is unavailable).
    cache_db.db_set(key, data, fmt)


def clear_cache(key: str, fmt: str = "json") -> bool:
    """Delete a single cache entry from both tiers. Returns True if the file existed."""
    cache_db.db_delete(key)
    path = _cache_path(key, fmt)
    if path.exists():
        path.unlink()
        return True
    return False
