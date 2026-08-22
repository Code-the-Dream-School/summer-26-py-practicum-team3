# services/pipeline/tests/transform/test_transform.py

from datetime import datetime, timezone

import pytest
from pipeline.transform import transform


def test_transform_successful_response(load_fixture):
    """Transform a representative raw response into clean air-quality records."""
    raw_response = load_fixture("air_pollution_success.json")

    result = transform(raw_response)

    assert len(result) == 2

    record = result[0]

    assert record["city_id"] == "us-san-francisco-ca"
    assert record["city_name"] == "San Francisco"
    assert record["country_code"] == "US"
    assert record["state_code"] == "CA"
    assert record["lat"] == 37.7749
    assert record["lon"] == -122.4194

    assert record["observed_at"] == datetime(
        2024, 7, 3, 12, 26, 40, tzinfo=timezone.utc
    )

    assert record["aqi"] == 2
    assert record["aqi_label"] == "Fair"
    assert record["co"] == 201.94
    assert record["no"] == 0.0
    assert record["no2"] == 1.2
    assert record["o3"] == 68.6
    assert record["so2"] == 0.6
    assert record["pm2_5"] == 4.3
    assert record["pm10"] == 5.1
    assert record["nh3"] == 0.12

    assert record["run_id"] == "run-2024-07-03-001"
    assert record["pipeline_run_id"] == "pipeline-2024-07-03-001"


def test_transform_carries_extraction_context_to_every_record(load_fixture):
    """Copy location and pipeline context to every transformed observation."""
    raw_response = load_fixture("air_pollution_success.json")

    result = transform(raw_response)

    assert len(result) == 2

    for record in result:
        assert record["city_id"] == raw_response["city_id"]
        assert record["city_name"] == raw_response["city_name"]
        assert record["country_code"] == raw_response["country_code"]
        assert record["state_code"] == raw_response["state_code"]
        assert record["lat"] == raw_response["lat"]
        assert record["lon"] == raw_response["lon"]
        assert record["run_id"] == raw_response["run_id"]
        assert record["pipeline_run_id"] == raw_response["pipeline_run_id"]


def test_transform_empty_response_returns_empty_list(load_fixture):
    """Return no records when the raw response contains an empty observation list."""
    raw_response = load_fixture("air_pollution_empty.json")

    result = transform(raw_response)

    assert result == []


def test_transform_handles_missing_optional_fields(load_fixture):
    """Transform a response when an optional context or measurement field is absent."""
    raw_response = load_fixture("air_pollution_missing_optional.json")

    result = transform(raw_response)

    assert len(result) == 1

    record = result[0]

    assert record["city_id"] == "us-san-francisco-ca"
    assert record["city_name"] == "San Francisco"
    assert record["country_code"] == "US"
    assert record["state_code"] is None

    assert record["aqi"] == 2
    assert record["co"] == 201.94
    assert record["pm2_5"] == 4.3


def test_transform_rejects_missing_required_field(load_fixture):
    """Raise an error when a required observation field is missing."""
    raw_response = load_fixture("air_pollution_missing_required.json")

    with pytest.raises(ValueError):
        transform(raw_response)


def test_transform_deduplicates_repeated_timestamps(load_fixture):
    """Keep one clean record when multiple observations share the same timestamp."""
    raw_response = load_fixture("air_pollution_duplicate_timestamps.json")

    result = transform(raw_response)

    assert len(result) == 1