"""Unit tests for the Extract stage contract adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pipeline.extract.openweather_air_pollution import (
    RawAirPollutionRecord,
    to_transform_input,
)


def test_to_transform_input_maps_fields_correctly():
    """Verifies that RawAirPollutionRecord correctly translates to the Transform envelope."""
    ts = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)
    record = RawAirPollutionRecord(
        city="Seattle",
        country_code="US",
        lat=47.6062,
        lon=-122.3321,
        start=ts,
        end=ts,
        run_id="run-001",
        pipeline_run_id=10,
        status="ok",
        raw_response={"list": [{"dt": 1720000000}]},
        raw_file_path=Path("/tmp/raw.json"),
        city_id="us-seattle-wa",
        state_code="WA",
        retrieved_at=ts,
    )

    result = to_transform_input(record)

    assert result["status"] == "ok"
    assert result["payload"] == {"list": [{"dt": 1720000000}]}
    assert result["city_id"] == "us-seattle-wa"
    assert result["city_name"] == "Seattle"
    assert result["country_code"] == "US"
    assert result["state_code"] == "WA"
    assert result["lat"] == 47.6062
    assert result["lon"] == -122.3321
    assert result["retrieved_at"] == ts
    assert isinstance(result["retrieved_at"], datetime)
    assert result["run_id"] == "run-001"
    assert result["pipeline_run_id"] == 10