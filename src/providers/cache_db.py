"""
Postgres-backed persistence layer for the provider cache.

This is the durable tier behind providers/cache.py. The local file cache
(data/cache/) still works for development and as a fast local tier, but on
ephemeral hosts (Railway) it is wiped on every restart. Mirroring entries into
the provider_cache table makes them survive restarts/redeploys.

Design rules
------------
- Never raise to the caller. If DATABASE_URL is missing, the table does not
  exist, or any query fails, every function degrades to a no-op / None so the
  file cache transparently takes over.
- Availability is probed once and memoised, so a configured-but-unreachable DB
  does not add a failed connection attempt to every single cache lookup.
- txt payloads are wrapped as {"__text__": <str>} so a single JSONB column can
  store both the JSON provider responses and raw filing text.

Schema: see db/migrations/001_provider_cache.sql
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Tri-state availability cache: None = not yet probed, True/False = result.
_DB_ENABLED: bool | None = None

_TEXT_WRAP_KEY = "__text__"


def _probe() -> bool:
    """
    Return True if a usable provider_cache table is reachable.
    Probed once and memoised. Any failure disables the DB tier for this process.
    """
    global _DB_ENABLED
    if _DB_ENABLED is not None:
        return _DB_ENABLED

    try:
        import db as _db  # src/ is on sys.path in the backend

        if not _db.is_configured():
            _DB_ENABLED = False
            return False

        from sqlalchemy import text

        with _db.get_db_session() as conn:
            conn.execute(text("SELECT 1 FROM provider_cache LIMIT 1"))
        _DB_ENABLED = True
        logger.info("provider_cache: Postgres persistence enabled")
    except Exception as exc:
        _DB_ENABLED = False
        logger.warning(
            "provider_cache: Postgres persistence disabled, falling back to "
            "file cache only (%s)", exc
        )
    return _DB_ENABLED


def available() -> bool:
    """Public, side-effect-free-ish availability check (triggers one probe)."""
    return _probe()


def db_get(key: str, ttl_seconds: int, fmt: str = "json") -> "dict | list | str | None":
    """
    Return a fresh cached value for *key* from Postgres, or None.

    Freshness is computed from fetched_at against *ttl_seconds*. Returns None on
    any error so the caller falls back to the file cache.
    """
    if not _probe():
        return None
    try:
        import db as _db
        from sqlalchemy import text

        with _db.get_db_session() as conn:
            row = conn.execute(
                text("""
                    SELECT payload
                    FROM provider_cache
                    WHERE cache_key = :k
                      AND fetched_at > now() - make_interval(secs => :ttl)
                """),
                {"k": key, "ttl": float(ttl_seconds)},
            ).fetchone()
    except Exception as exc:
        logger.warning("provider_cache db_get failed for %s: %s", key, exc)
        return None

    if row is None:
        return None

    payload = row[0]
    # SQLAlchemy may hand back JSONB as a parsed object or as a JSON string,
    # depending on driver/types — normalise both.
    if isinstance(payload, (str, bytes)):
        try:
            payload = json.loads(payload)
        except (ValueError, TypeError):
            return None

    if fmt != "json" and isinstance(payload, dict) and _TEXT_WRAP_KEY in payload:
        return payload[_TEXT_WRAP_KEY]
    return payload


def db_set(key: str, data: "dict | list | str", fmt: str = "json") -> None:
    """
    Upsert *data* into provider_cache under *key*, refreshing fetched_at.
    No-op (and never raises) when the DB tier is unavailable.
    """
    if not _probe():
        return

    payload: Any = {_TEXT_WRAP_KEY: data} if fmt != "json" else data
    try:
        import db as _db
        from sqlalchemy import text

        with _db.get_db_session() as conn:
            conn.execute(
                text("""
                    INSERT INTO provider_cache (cache_key, payload, fetched_at)
                    VALUES (:k, CAST(:p AS jsonb), now())
                    ON CONFLICT (cache_key) DO UPDATE SET
                        payload    = EXCLUDED.payload,
                        fetched_at = now()
                """),
                {"k": key, "p": json.dumps(payload, ensure_ascii=False)},
            )
    except Exception as exc:
        logger.warning("provider_cache db_set failed for %s: %s", key, exc)


def db_delete(key: str) -> None:
    """Delete a single entry from provider_cache. No-op when unavailable."""
    if not _probe():
        return
    try:
        import db as _db
        from sqlalchemy import text

        with _db.get_db_session() as conn:
            conn.execute(
                text("DELETE FROM provider_cache WHERE cache_key = :k"), {"k": key}
            )
    except Exception as exc:
        logger.warning("provider_cache db_delete failed for %s: %s", key, exc)
