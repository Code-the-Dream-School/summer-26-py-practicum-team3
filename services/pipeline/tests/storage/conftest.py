import os
from pathlib import Path
from typing import Iterator

import psycopg
import pytest

from alembic import command
from alembic.config import Config

from sqlalchemy.engine import make_url
from dotenv import load_dotenv
load_dotenv(dotenv_path="services/pipeline/.env")


@pytest.fixture(scope="session")
def setup_test_database():
    """Ensure test DB exists and return its URL. Skip suite if unavailable."""
    raw_url = os.getenv("TEST_DATABASE_URL")
    if not raw_url :
        pytest.skip("Postgres URL not set")

    url = make_url(raw_url)
    database_name = url.database
    if not database_name.endswith("_test"):
        raise RuntimeError(
            f"Unsafe TEST_DATABASE_URL detected: /{database_name}\n"
            "Storage tests require a database name ending with '_test'."
        )

    db_url  = raw_url.replace("postgresql+psycopg://", "postgresql://", 1)
    server_url = db_url .rsplit("/", 1)[0] + "/postgres"

    try:
        with psycopg.connect(server_url) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s;",
                    (database_name,)
                )
                exists = cur.fetchone()
                if not exists:
                    cur.execute(f'CREATE DATABASE "{database_name}"')
    except Exception as exc:
        pytest.skip(f"Postgres unreachable: {exc}")

    return db_url


@pytest.fixture(scope="session")
def migrated_schema(setup_test_database, pytestconfig):
    """Apply Alembic migrations before running tests."""
    db_url = setup_test_database
    root = pytestconfig.rootpath

    ini_path = root / "services" / "pipeline" / "alembic.ini"
    script_dir = root / "services" / "pipeline" / "alembic"

    alembic_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1).replace("%", "%%")

    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", alembic_url)
    cfg.set_main_option("script_location", str(script_dir))

    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    return db_url

