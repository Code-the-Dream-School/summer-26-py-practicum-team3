"""Integration tests for the full orchestration path against a real PostgreSQL test database.

Extract's network calls (geocoding, OpenWeather) are stubbed so these tests don't depend on a
live API key or network access; transform and load run for real against `migrated_schema` /
`db_connection`'s test database, so this exercises the actual Postgres writes end to end.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from pydantic import SecretStr

from pipeline.common import config
from pipeline.extract.cities import City
from pipeline.extract.geocoding import Coordinates
from pipeline.extract.openweather_air_pollution import RawAirPollutionRecord
from pipeline.orchestration import run_pipeline_job
from pipeline.run_tracking import _default_repository, list_pipeline_runs

CITY = City(
    city_id="us-testville-tx",
    city_name="Testville",
    country_code="US",
    state_code="TX",
    timezone="America/Chicago",
    active=True,
)


def _fake_geocode_city(*, city, country_code, state, raw_dir):
    return Coordinates(
        lat=30.2672,
        lon=-97.7431,
        source="geocoded",
        http_status=200,
        payload={"name": city, "lat": 30.2672, "lon": -97.7431, "country": country_code},
    )


def _fake_fetch_air_pollution_history(
    *, raw_dir, city_id, city, country_code, state_code, lat, lon, start, end, run_id, pipeline_run_id
):
    observed_at = end - timedelta(hours=1)
    payload = {
        "list": [
            {
                "dt": int(observed_at.timestamp()),
                "main": {"aqi": 2},
                "components": {
                    "co": 200.0, "no": 0.1, "no2": 5.0, "o3": 40.0,
                    "so2": 1.0, "pm2_5": 8.0, "pm10": 12.0, "nh3": 0.5,
                },
            }
        ]
    }
    return RawAirPollutionRecord(
        city=city,
        country_code=country_code,
        lat=lat,
        lon=lon,
        start=start,
        end=end,
        run_id=run_id,
        pipeline_run_id=pipeline_run_id,
        status="ok",
        raw_response=payload,
        raw_file_path=None,
        city_id=city_id,
        state_code=state_code,
        retrieved_at=datetime.now(timezone.utc),
    )


def _count(conn: psycopg.Connection, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table};")
        (count,) = cur.fetchone()
    return count


@pytest.fixture
def postgres_configured(monkeypatch: pytest.MonkeyPatch, db_connection, migrated_schema, tmp_path):
    """Point the pipeline's Settings at the real test database and a scratch raw/gold dir.

    `migrated_schema` gives the actual DSN string (with real credentials) to hand to Settings;
    `db_connection` is a separate connection used to verify writes and to truncate afterward —
    run_pipeline_job opens its own connection(s) internally rather than reusing either of these.
    """
    monkeypatch.setattr(config.settings, "database_url", SecretStr(migrated_schema))
    monkeypatch.setattr(config.settings, "raw_dir", str(tmp_path / "raw"))
    monkeypatch.setattr(config.settings, "gold_dir", str(tmp_path / "gold"))
    monkeypatch.setattr("pipeline.orchestration.read_cities", lambda path: [CITY])
    monkeypatch.setattr("pipeline.orchestration.geocode_city", _fake_geocode_city)
    monkeypatch.setattr("pipeline.orchestration.fetch_air_pollution_history", _fake_fetch_air_pollution_history)
    return db_connection


def test_run_pipeline_job_persists_all_tables_on_success(postgres_configured):
    conn = postgres_configured

    result = run_pipeline_job(source="test")

    assert _count(conn, "cities") == 1
    assert _count(conn, "raw_geocoding_responses") == 1
    assert _count(conn, "raw_air_pollution_responses") == 1
    assert _count(conn, "air_pollution_gold") == 1
    assert _count(conn, "pipeline_runs") == 1

    with conn.cursor() as cur:
        cur.execute("SELECT status, error_message FROM pipeline_runs WHERE run_id = %s;", (result.run_id,))
        status, error_message = cur.fetchone()

    assert status == "succeeded"
    assert error_message is None

    # Prove list_pipeline_runs() reads from Postgres, not the in-memory singleton.
    _default_repository.clear()
    runs = list_pipeline_runs(limit=10)
    assert any(r.run_id == result.run_id for r in runs)


def _raise_boom(envelope):
    raise RuntimeError("boom")


def test_run_pipeline_job_marks_run_failed_and_keeps_raw_rows(postgres_configured, monkeypatch: pytest.MonkeyPatch):
    conn = postgres_configured
    monkeypatch.setattr("pipeline.orchestration.transform_raw_response", _raise_boom)

    with pytest.raises(RuntimeError, match="boom"):
        run_pipeline_job(source="test")

    # Extract already committed cities + raw rows before transform blew up.
    assert _count(conn, "cities") == 1
    assert _count(conn, "raw_geocoding_responses") == 1
    assert _count(conn, "raw_air_pollution_responses") == 1
    assert _count(conn, "air_pollution_gold") == 0

    with conn.cursor() as cur:
        cur.execute("SELECT status, error_message FROM pipeline_runs;")
        status, error_message = cur.fetchone()

    assert status == "failed"
    assert "boom" in error_message


def _raise_connection_blip():
    raise RuntimeError("connection blip")


def test_run_pipeline_job_marks_run_failed_when_extract_connection_fails(
    postgres_configured, monkeypatch: pytest.MonkeyPatch
):
    """A transient connection failure *after* the pipeline_runs row exists must not leave it
    stuck at status='running' — it must be marked failed like any other stage failure."""
    conn = postgres_configured
    monkeypatch.setattr("pipeline.orchestration.get_connection", _raise_connection_blip)

    with pytest.raises(RuntimeError, match="connection blip"):
        run_pipeline_job(source="test")

    assert _count(conn, "pipeline_runs") == 1

    with conn.cursor() as cur:
        cur.execute("SELECT status, error_message FROM pipeline_runs;")
        status, error_message = cur.fetchone()

    assert status == "failed"
    assert "connection blip" in error_message
