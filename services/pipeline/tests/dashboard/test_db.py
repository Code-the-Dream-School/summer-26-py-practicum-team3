"""Tests for dashboard database connection helpers."""

from __future__ import annotations

import pytest

from dashboard.db import _to_psycopg_dsn


@pytest.mark.parametrize(
    "database_url,expected",
    [
        (
            "postgresql+psycopg://vasilisolap@localhost:5432/city_air_tracker",
            "postgresql://vasilisolap@localhost:5432/city_air_tracker",
        ),
        (
            "postgresql+psycopg2://user:pass@localhost:5432/db",
            "postgresql://user:pass@localhost:5432/db",
        ),
        (
            "postgres+psycopg://user@host/db",
            "postgres://user@host/db",
        ),
        (
            # Already in the plain form psycopg expects - passes through unchanged.
            "postgresql://plain@localhost:5432/db",
            "postgresql://plain@localhost:5432/db",
        ),
    ],
)
def test_to_psycopg_dsn_strips_sqlalchemy_driver_suffix(database_url: str, expected: str) -> None:
    """DATABASE_URL is documented/used elsewhere (alembic/env.py via SQLAlchemy) in
    the "dialect+driver" form (e.g. postgresql+psycopg://...), but raw
    psycopg.connect() only understands postgresql:// / postgres:// and raises a
    confusing 'missing "=" ... in connection info string' error on the +driver
    suffix. This normalization lets both consumers share one DATABASE_URL value.
    """
    assert _to_psycopg_dsn(database_url) == expected
