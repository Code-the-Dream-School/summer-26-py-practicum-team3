"""Database connection helpers for the dashboard service."""

from __future__ import annotations

from typing import Any

import psycopg
from pipeline.common.db import normalize_dsn
from psycopg.rows import dict_row

from dashboard.config import settings


def get_connection() -> psycopg.Connection[dict[str, Any]]:
    """Open and return a new PostgreSQL connection using dict_row factory.

    Note on connection lifecycle and caching:
        Callers (e.g., Streamlit views) are responsible for managing the connection
        lifecycle. In Streamlit applications, wrap the connection provider in
        `@st.cache_resource` to avoid opening a new TCP connection on every page rerun:

        >>> import streamlit as st
        >>> from dashboard.db import get_connection
        >>>
        >>> @st.cache_resource
        >>> def init_connection():
        ...     return get_connection()

    The connection operates in autocommit mode because the dashboard layer 
    is strictly read-only.

    Raises:
        ValueError: If DATABASE_URL is not configured in the environment or .env file.
    """
    db_url = settings.database_url.get_secret_value()
    if not db_url:
        raise ValueError("DATABASE_URL must be configured in environment or .env file.")

    return psycopg.connect(normalize_dsn(db_url), row_factory=dict_row, autocommit=True)