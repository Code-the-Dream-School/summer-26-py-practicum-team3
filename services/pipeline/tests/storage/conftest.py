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


@pytest.fixture
def db_connection(setup_test_database, migrated_schema):
    """Real psycopg connection, truncated after each test."""
    conn = psycopg.connect(setup_test_database)
    try:
        yield conn
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("""
                TRUNCATE TABLE
                    air_pollution_gold,
                    raw_air_pollution_responses,
                    raw_geocoding_responses,
                    pipeline_runs,
                    cities
                RESTART IDENTITY CASCADE;
            """)
        conn.commit()
        conn.close()


@pytest.fixture
def seeded_city_and_run(db_connection):
    """Insert one city + one pipeline_run required for FK-dependent tests."""
    with db_connection.cursor() as cur:
        cur.execute("""
            INSERT INTO cities (city_id, city_name, country_code, timezone, active)
            VALUES ('us-los-angeles-ca', 'Los Angeles', 'US', 'America/Los_Angeles', true)
            RETURNING city_id;
        """)
        (city_id,) = cur.fetchone()

        cur.execute("""
            INSERT INTO pipeline_runs (run_id, source, history_hours, window_start_utc,
                window_end_utc, status, city_count, raw_response_count, gold_row_count)
            VALUES ('test-run-1', 'test', 1, NOW(), NOW(), 'running', 0, 0, 0)
            RETURNING pipeline_run_id
        """)
        (pipeline_run_id,) = cur.fetchone()

    return city_id, pipeline_run_id
