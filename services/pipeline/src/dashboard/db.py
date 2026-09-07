"""Database connection helpers for the dashboard's read-only data-serving layer."""

from __future__ import annotations

import re
from typing import Any

import psycopg
import streamlit as st
from psycopg.rows import dict_row

from dashboard.config import settings

# DATABASE_URL is documented (docs/setup/environment_profiles_guide.md) and used
# elsewhere in this project (alembic/env.py, via SQLAlchemy) in SQLAlchemy's
# "dialect+driver" URL form, e.g. postgresql+psycopg://... . Raw psycopg.connect(),
# used here, only understands the plain "postgresql://" / "postgres://" schemes and
# raises on the "+driver" suffix ("missing "=" after ... in connection info string"),
# so strip it rather than requiring a second, differently-formatted env var.
_SQLALCHEMY_DRIVER_SUFFIX = re.compile(r"^(postgresql|postgres)\+[\w]+://")


def _to_psycopg_dsn(database_url: str) -> str:
    """Normalize a SQLAlchemy-style DATABASE_URL for raw psycopg.connect()."""
    return _SQLALCHEMY_DRIVER_SUFFIX.sub(r"\1://", database_url)


def get_connection() -> psycopg.Connection[dict[str, Any]]:
    """Open and return a new PostgreSQL connection using dict_row factory.

    The connection operates in autocommit mode because the dashboard layer is
    strictly read-only: without it every SELECT would leave an idle transaction
    open for the lifetime of the cached connection.

    Prefer `init_connection()` below in Streamlit code — it caches this
    connection across reruns instead of opening a new TCP connection each time.

    Raises:
        ValueError: If DATABASE_URL is not configured in the environment or .env file."""
    
    db_url = settings.database_url.get_secret_value()
    if not db_url:
        raise ValueError("DATABASE_URL must be configured in environment or .env file.")
    
    return psycopg.connect(_to_psycopg_dsn(db_url), row_factory=dict_row, autocommit=True)


@st.cache_resource
def init_connection() -> psycopg.Connection[dict[str, Any]]:
    """Return a cached database connection, shared across Streamlit reruns.

    Lives here rather than in app.py so that page modules can import it without
    executing app.py's top-level UI code (which would render the landing
    banner a second time on top of the page).
    """
    return get_connection()