"""Tests for dashboard database connection helpers."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from dashboard import db
from pipeline.common.db import normalize_dsn


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
            "postgresql://user@host/db",
        ),
        (
            # Already in the plain form psycopg expects - passes through unchanged.
            "postgresql://plain@localhost:5432/db",
            "postgresql://plain@localhost:5432/db",
        ),
    ],
)
def test_normalize_dsn_strips_sqlalchemy_driver_suffix(database_url: str, expected: str) -> None:
    """DATABASE_URL is documented/used elsewhere (alembic/env.py via SQLAlchemy) in
    the "dialect+driver" form (e.g. postgresql+psycopg://...), but raw
    psycopg.connect() only understands postgresql:// / postgres:// and raises a
    confusing 'missing "=" ... in connection info string' error on the +driver
    suffix. This normalization lets both consumers share one DATABASE_URL value.
    """
    assert normalize_dsn(database_url) == expected


def test_get_connection_unwraps_the_secret_and_normalizes_the_dsn(monkeypatch) -> None:
    """get_connection() must hand psycopg a plain, normalized connection string.

    database_url is a SecretStr, so it has to be unwrapped before the regex
    normalization runs — passing the SecretStr through would fail at connect time,
    which no mock-based page test would catch.
    """
    monkeypatch.setattr(
        db.settings, "database_url", SecretStr("postgresql+psycopg://user@localhost:5432/db")
    )
    captured: dict[str, object] = {}

    def fake_connect(dsn, **kwargs):
        captured["dsn"] = dsn
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(db.psycopg, "connect", fake_connect)
    db.get_connection()

    assert captured["dsn"] == "postgresql://user@localhost:5432/db"
    # The dashboard is read-only: without autocommit every SELECT leaves an
    # idle transaction open on the cached connection.
    assert captured["kwargs"]["autocommit"] is True


def test_get_connection_requires_database_url(monkeypatch) -> None:
    """An unset DATABASE_URL raises ValueError, which pages render as an error state."""
    monkeypatch.setattr(db.settings, "database_url", SecretStr(""))

    with pytest.raises(ValueError, match="DATABASE_URL"):
        db.get_connection()
