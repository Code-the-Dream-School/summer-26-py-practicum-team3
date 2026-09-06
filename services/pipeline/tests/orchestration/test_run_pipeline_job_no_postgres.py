"""Tests that run_pipeline_job() degrades gracefully to Parquet-only when DATABASE_URL is unset.

No real database involved here — extract's network calls are stubbed, and Postgres persistence
should be skipped entirely since `database_url` is forced empty.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pipeline.common import config
from pipeline.extract.cities import City
from pipeline.extract.geocoding import Coordinates
from pipeline.extract.openweather_air_pollution import RawAirPollutionRecord
from pipeline.orchestration import run_pipeline_job
from pipeline.run_tracking import _default_repository
from pydantic import SecretStr

CITY = City(
    city_id="us-testville-tx",
    city_name="Testville",
    country_code="US",
    state_code="TX",
    timezone="America/Chicago",
    active=True,
)


def _fake_geocode_city(*, city, country_code, state, raw_dir):
    return Coordinates(lat=30.2672, lon=-97.7431, source="geocoded")


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


def test_run_pipeline_job_succeeds_and_writes_parquet_only_when_database_url_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(config.settings, "database_url", SecretStr(""))
    monkeypatch.setattr(config.settings, "raw_dir", str(tmp_path / "raw"))
    monkeypatch.setattr(config.settings, "gold_dir", str(tmp_path / "gold"))
    monkeypatch.setattr("pipeline.orchestration.read_cities", lambda path: [CITY])
    monkeypatch.setattr("pipeline.orchestration.geocode_city", _fake_geocode_city)
    monkeypatch.setattr("pipeline.orchestration.fetch_air_pollution_history", _fake_fetch_air_pollution_history)

    _default_repository.clear()
    try:
        result = run_pipeline_job(source="test")
    finally:
        _default_repository.clear()

    assert result.city_count == 1
    assert result.raw_response_count == 1
    assert result.gold_row_count == 1
    assert result.gold_path is not None
    assert result.gold_path.exists()
