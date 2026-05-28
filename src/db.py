"""
src/db.py

SQLAlchemy engine and session utilities for the Portfolio Risk backend.

Only the FastAPI backend imports this module.
DATABASE_URL must never appear in any NEXT_PUBLIC_ variable or frontend code.

Environment variable required
------------------------------
DATABASE_URL  Supabase pooler (recommended):
                postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
              Supabase direct connection (alternative):
                postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres

Pooler note
-----------
Supabase's pgbouncer runs in transaction mode (port 6543).
Transaction mode does not support prepared statements or session-level settings.
When a pooler URL is detected (port 6543 or ?pgbouncer=true), this module
automatically switches to NullPool so SQLAlchemy does not maintain its own
connection pool on top of pgbouncer.

Usage
-----
from db import get_db_session

with get_db_session() as conn:
    result = conn.execute(text("SELECT 1"))
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.pool import NullPool

_engine = None


def _get_engine():
    global _engine
    if _engine is not None:
        return _engine

    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. "
            "Add it to your .env file:\n"
            "  DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres"
        )

    # Normalize Supabase / Heroku-style postgres:// → postgresql://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    # Detect Supabase pooler: port 6543 or explicit pgbouncer flag in URL
    is_pooler = ":6543" in url or "pgbouncer=true" in url.lower()

    if is_pooler:
        # pgbouncer transaction mode: do not maintain a SQLAlchemy connection
        # pool on top of pgbouncer — use NullPool (one connection per request).
        _engine = create_engine(
            url,
            poolclass=NullPool,
            connect_args={"connect_timeout": 10, "sslmode": "require"},
        )
    else:
        # Direct PostgreSQL connection (port 5432) — standard pool is fine.
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            connect_args={"connect_timeout": 10},
        )
    return _engine


@contextmanager
def get_db_session() -> Generator[Connection, None, None]:
    """
    Yield an auto-committing SQLAlchemy Connection.

    On normal exit the transaction is committed.
    On exception it is rolled back automatically.

    Example
    -------
    with get_db_session() as conn:
        conn.execute(text("INSERT INTO ..."), params)
    """
    with _get_engine().begin() as conn:
        yield conn


def is_configured() -> bool:
    """Return True if DATABASE_URL is present in the environment."""
    return bool(os.environ.get("DATABASE_URL", "").strip())
