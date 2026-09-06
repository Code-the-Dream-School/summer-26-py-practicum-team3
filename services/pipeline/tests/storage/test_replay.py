"""Integration tests for replaying transform/load from Postgres without a new API call."""

from __future__ import annotations

import psycopg
import pytest
from pydantic import SecretStr

from pipeline.common import config
from pipeline.orchestration import run_pipeline_job, run_replay_job


def _fake_geocode_city(*, city, country_code, state, raw_dir):
    from pipeline.extract.geocoding import Coordinates

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
    from datetime import datetime, timedelta, timezone

    from pipeline.extract.openweather_air_pollution import RawAirPollutionRecord

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
def seeded_source_run(monkeypatch: pytest.MonkeyPatch, db_connection, migrated_schema, tmp_path):
    """Run a real pipeline job (extract stubbed) to seed a source run's raw responses for replay."""
    from pipeline.extract.cities import City

    city = City(
        city_id="us-testville-tx",
        city_name="Testville",
        country_code="US",
        state_code="TX",
        timezone="America/Chicago",
        active=True,
    )

    monkeypatch.setattr(config.settings, "database_url", SecretStr(migrated_schema))
    monkeypatch.setattr(config.settings, "raw_dir", str(tmp_path / "raw"))
    monkeypatch.setattr(config.settings, "gold_dir", str(tmp_path / "gold"))
    monkeypatch.setattr("pipeline.orchestration.read_cities", lambda path: [city])
    monkeypatch.setattr("pipeline.orchestration.geocode_city", _fake_geocode_city)
    monkeypatch.setattr("pipeline.orchestration.fetch_air_pollution_history", _fake_fetch_air_pollution_history)

    source_result = run_pipeline_job(source="test")
    return db_connection, source_result.run_id


def test_run_replay_job_produces_new_gold_rows_without_calling_api(seeded_source_run, monkeypatch):
    conn, source_run_id = seeded_source_run

    def _fail_if_called(*args, **kwargs):
        pytest.fail("replay must not call fetch_air_pollution_history")

    monkeypatch.setattr("pipeline.orchestration.fetch_air_pollution_history", _fail_if_called)
    monkeypatch.setattr("pipeline.orchestration.geocode_city", _fail_if_called)

    result = run_replay_job(source_run_id=source_run_id)

    assert result.run_id != source_run_id
    assert result.gold_row_count == 1

    with conn.cursor() as cur:
        cur.execute(
            "SELECT status, pipeline_run_id FROM pipeline_runs WHERE run_id = %s;",
            (result.run_id,),
        )
        status, replay_pipeline_run_id = cur.fetchone()
        cur.execute(
            "SELECT status, pipeline_run_id FROM pipeline_runs WHERE run_id = %s;",
            (source_run_id,),
        )
        _, source_pipeline_run_id = cur.fetchone()

    assert status == "succeeded"
    assert replay_pipeline_run_id > source_pipeline_run_id

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM air_pollution_gold WHERE pipeline_run_id = %s;",
            (replay_pipeline_run_id,),
        )
        (gold_count,) = cur.fetchone()

    assert gold_count == 1


def test_run_replay_job_raises_clear_error_for_unknown_run_id(seeded_source_run):
    conn, _ = seeded_source_run

    with pytest.raises(ValueError, match="does-not-exist"):
        run_replay_job(source_run_id="does-not-exist")


def test_run_replay_job_requires_database_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config.settings, "database_url", SecretStr(""))

    with pytest.raises(ValueError, match="DATABASE_URL"):
        run_replay_job(source_run_id="anything")
