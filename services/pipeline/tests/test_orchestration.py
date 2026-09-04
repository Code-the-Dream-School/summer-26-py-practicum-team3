from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from pipeline.extract.cities import City
from pipeline.extract.openweather_air_pollution import RawAirPollutionRecord
from pipeline.orchestration import run_extract_stage


@patch("pipeline.orchestration.fetch_air_pollution_history")
@patch("pipeline.orchestration.geocode_city")
@patch("pipeline.orchestration.read_cities")
def test_run_extract_stage_skips_city_when_geocoding_fails(
    mock_read_cities,
    mock_geocode_city,
    mock_fetch_history,
    caplog,
    tmp_path: Path
):
    """Verifies that the extract stage skips processing for a city and logs a warning if geocoding returns None."""
    caplog.set_level(logging.WARNING)
    
    city_berlin = City(
        city_id="de-berlin",
        city_name="Berlin",
        country_code="DE",
        timezone="Europe/Berlin",
        active=True
    )
    
    city_nowhere = City(
        city_id="fr-nowhere",
        city_name="Nowhere",
        country_code="FR",
        timezone="UTC",
        active=True
    )
    
    mock_read_cities.return_value = [city_berlin, city_nowhere]
    
    def geocode_side_effect(city, country_code, state=None, raw_dir=None, **kwargs):
        if city == "Berlin":
            from pipeline.extract.geocoding import Coordinates
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
    
    raw_records, total_cities = run_extract_stage(
        raw_dir=tmp_path,
        start=start_time,
        end=end_time,
        run_id="run-123",
        pipeline_run_id=1
    )
    
    assert len(raw_records) == 1
    assert raw_records[0] == dummy_record
    assert total_cities == 2
    
    mock_fetch_history.assert_called_once()
    _, kwargs = mock_fetch_history.call_args
    assert kwargs["city"] == "Berlin"
    
    warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any(getattr(r, "city", None) == "Nowhere" for r in warning_records)