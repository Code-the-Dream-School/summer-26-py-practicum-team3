"""Unit tests for the orchestration layer."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from pipeline.extract.cities import City
from pipeline.extract.geocoding import Coordinates
from pipeline.extract.openweather_air_pollution import RawAirPollutionRecord
from pipeline.orchestration import run_extract_stage


@patch("pipeline.orchestration.fetch_air_pollution_history")
@patch("pipeline.orchestration.geocode_city")
def test_run_extract_stage_skips_city_when_geocoding_fails(
    mock_geocode_city,
    mock_fetch_history,
    caplog,
    tmp_path: Path
):
    """Verifies that the extract stage skips processing for a city and logs a warning if geocoding returns None."""
    # 1. Setup mock data and capture logs
    caplog.set_level(logging.WARNING)

    city_berlin = City(
        city_id="de-berlin",
        city_name="Berlin",
        country_code="DE",
        timezone="Europe/Berlin",
        active=True
    )
    
    # Using a valid ISO country code ("FR") to pass the pycountry validation
    city_nowhere = City(
        city_id="fr-nowhere",
        city_name="Nowhere",
        country_code="FR",
        timezone="UTC",
        active=True
    )
    
    cities = [city_berlin, city_nowhere]

    def geocode_side_effect(raw_dir, city, country_code, state):
        if city == "Berlin":
            return Coordinates(lat=52.52, lon=13.405, source="geocoded")
        return None

    mock_geocode_city.side_effect = geocode_side_effect

    dummy_record = RawAirPollutionRecord(
        city="Berlin",
        country_code="DE",
        lat=52.52,
        lon=13.405,
        start=datetime(2026, 8, 30, tzinfo=timezone.utc),
        end=datetime(2026, 8, 30, tzinfo=timezone.utc),
        run_id="run-123",
        pipeline_run_id=1,
        status="ok",
        raw_response={"list": []},
        raw_file_path=None,
        city_id="de-berlin",
        state_code=None,
        retrieved_at=datetime.now(timezone.utc)
    )
    mock_fetch_history.return_value = dummy_record

    start_time = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 8, 30, 1, 0, tzinfo=timezone.utc)

    # 2. Execute
    raw_records, total_cities = run_extract_stage(
        raw_dir=tmp_path,
        cities=cities,
        start=start_time,
        end=end_time,
        run_id="run-123",
        pipeline_run_id=1
    )

    # 3. Assertions
    # Ensure the orchestrator attempted to process both cities
    assert total_cities == 2
    
    # Ensure only one record was added to the final list
    assert len(raw_records) == 1
    assert raw_records[0] == dummy_record
    
    # Ensure the weather API was called exactly once, and only for Berlin
    assert mock_fetch_history.call_count == 1
    assert mock_fetch_history.call_args.kwargs["city"] == "Berlin"
    
    # Ensure a warning was logged for the skipped city by inspecting LogRecord attributes
    warning_records = [
        record for record in caplog.records 
        if record.levelname == "WARNING" and "Geocoding failed" in record.message
    ]
    
    assert len(warning_records) == 1
    # Verify the structured extra attribute was correctly bound to the log record
    assert getattr(warning_records[0], "city", None) == "Nowhere"