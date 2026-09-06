"""Shared PostgreSQL connection helper for the pipeline (write) side.

Distinct from `dashboard.db`, which is read-only and opens its connection in
autocommit mode. The pipeline writes and needs to control its own commit
points, so connections here are opened with normal (manual-commit) semantics.
"""

from __future__ import annotations

import re
from typing import Any

import psycopg

from pipeline.common.config import settings

_DSN_SCHEME_PATTERN = re.compile(r"^postgres(?:ql)?\+\w+://")


def normalize_dsn(url: str) -> str:
    """Strip any SQLAlchemy-style `+driver` suffix psycopg3 doesn't understand.

    Handles `postgresql+psycopg://` (what `.env`/Alembic actually use), and more
    generally `postgres+psycopg://` (no "ql"), `+psycopg2`, `+asyncpg`, etc. —
    psycopg3's `connect()` only recognizes a plain `postgresql://` / `postgres://`.
    """
    return _DSN_SCHEME_PATTERN.sub("postgresql://", url, count=1)


def get_connection() -> psycopg.Connection[Any]:
    """Open and return a new PostgreSQL connection for pipeline writes.

    Callers are responsible for the connection's lifecycle (commit/rollback
    boundaries, closing it when done).

    Raises:
        ValueError: If DATABASE_URL is not configured in the environment or .env file.
    """
    db_url = settings.database_url.get_secret_value()
    if not db_url:
        raise ValueError("DATABASE_URL must be configured in environment or .env file.")

    return psycopg.connect(normalize_dsn(db_url))
