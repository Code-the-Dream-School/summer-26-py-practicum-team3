"""Shared PostgreSQL connection helper for the pipeline (write) side.

Distinct from `dashboard.db`, which is read-only and opens its connection in
autocommit mode. The pipeline writes and needs to control its own commit
points, so connections here are opened with normal (manual-commit) semantics.
"""

from __future__ import annotations

from typing import Any

import psycopg

from pipeline.common.config import settings

_SQLALCHEMY_PSYCOPG_SCHEME = "postgresql+psycopg://"
_PSYCOPG_SCHEME = "postgresql://"


def normalize_dsn(url: str) -> str:
    """Strip the SQLAlchemy-style `+psycopg` driver suffix psycopg3 doesn't understand.

    `.env`'s DATABASE_URL is written as `postgresql+psycopg://...` (what Alembic's
    SQLAlchemy URL needs), but `psycopg.connect()` only recognizes `postgresql://`
    / `postgres://`.
    """
    if url.startswith(_SQLALCHEMY_PSYCOPG_SCHEME):
        return _PSYCOPG_SCHEME + url[len(_SQLALCHEMY_PSYCOPG_SCHEME):]
    return url


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
