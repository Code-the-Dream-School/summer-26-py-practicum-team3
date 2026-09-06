"""Unit tests for the shared pipeline (write-side) database connection helper."""

from __future__ import annotations

import pytest
from pipeline.common import config
from pipeline.common.db import get_connection, normalize_dsn
from pydantic import SecretStr


def test_normalize_dsn_strips_sqlalchemy_psycopg_scheme() -> None:
    assert normalize_dsn("postgresql+psycopg://user:pass@localhost:5432/db") == (
        "postgresql://user:pass@localhost:5432/db"
    )


def test_normalize_dsn_leaves_plain_postgresql_scheme_unchanged() -> None:
    url = "postgresql://user:pass@localhost:5432/db"
    assert normalize_dsn(url) == url


def test_get_connection_raises_when_database_url_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.settings, "database_url", SecretStr(""))

    with pytest.raises(ValueError):
        get_connection()
