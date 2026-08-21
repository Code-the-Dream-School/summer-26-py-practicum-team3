""" Unit tests for transform/operations.py """

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pipeline.transform.operations import (
    aqi_label,
    dedupe_records,
    normalize_aqi,
    normalize_component,
    normalize_components,
    normalize_coordinate,
    normalize_text,
    unix_to_utc_datetime,
    build_air_quality_record,
)


# --- Timestamp normalization tests ---

def test_unix_to_utc_datetime_converts_unix_seconds_to_utc():
    result = unix_to_utc_datetime(1720000000)

    assert result == datetime(2024, 7, 3, 9, 46, 40, tzinfo=timezone.utc)
    assert result.tzinfo == timezone.utc

def test_unix_to_utc_datetime_converts_correctly():
    assert unix_to_utc_datetime(1606223802) == datetime(
        2020, 11, 24, 13, 16, 42, tzinfo=timezone.utc
    )


def test_unix_to_utc_datetime_handles_missing_or_invalid():
    assert unix_to_utc_datetime(None) is None
    assert unix_to_utc_datetime("not-a-timestamp") is None


@pytest.mark.parametrize("value", [None, "not-a-timestamp", object()])
def test_unix_to_utc_datetime_returns_none_for_invalid_value(value):
    assert unix_to_utc_datetime(value) is None


# --- Coordinate normalization tests ---

def test_normalize_coordinate_valid():
    assert normalize_coordinate("51.512345", is_latitude=True) == 51.512345

def test_normalize_longitude_casts_to_float():
    assert normalize_coordinate(
        "-122.41941234",
        is_latitude=False,
    ) == -122.41941234


@pytest.mark.parametrize(
    "value,is_latitude",
    [
        (90.0001, True),
        (-90.0001, True),
        (180.0001, False),
        (-180.0001, False),
    ],
)
def test_normalize_coordinate_out_of_range(
    value, is_latitude
):
    assert normalize_coordinate(value, is_latitude=is_latitude) is None


@pytest.mark.parametrize(
    "value,is_latitude",
    [
        (90, True),
        (-90, True),
        (180, False),
        (-180, False),
    ],
)
def test_normalize_coordinate_accepts_boundary_values(
    value, is_latitude
):
    assert normalize_coordinate(value, is_latitude=is_latitude) == float(value)


@pytest.mark.parametrize("value", [None, "not-a-number", object()])
def test_normalize_coordinate_returns_none_for_non_numeric_value(value):
    assert normalize_coordinate(value, is_latitude=True) is None



# --- AQI normalization tests ---

@pytest.mark.parametrize(
    "value,expected",
    [
        (1, 1),
        (2, 2),
        (3, 3),
        (4, 4),
        (5, 5),
        ("1", 1),
        ("5", 5),
    ],
)
def test_normalize_aqi_accepts_values_1_through_5(value, expected):
    assert normalize_aqi(value) == expected


@pytest.mark.parametrize(
    "value",
    [None, 0, 6, -1, "invalid"],
)
def test_normalize_aqi_if_missing_or_invalid_values(value):
    assert normalize_aqi(value) is None


@pytest.mark.parametrize(
    "aqi,expected",
    [
        (1, "Good"),
        (2, "Fair"),
        (3, "Moderate"),
        (4, "Poor"),
        (5, "Very Poor"),
    ],
)
def test_aqi_label_maps_aqi_to_openweather_category(aqi, expected):
    assert aqi_label(aqi) == expected


def test_aqi_label_returns_none_for_missing_aqi():
    assert aqi_label(None) is None


def test_aqi_label_returns_none_for_invalid_aqi():
    assert aqi_label(99) is None


# --- Normalize pollutant components tests ---

@pytest.mark.parametrize(
    "value, expected",
    [
        (201.941, 201.94),
        ("201.941", 201.94),
        (0, 0.0),
        (4.3, 4.3),
    ],
)
def test_normalize_component_casts_to_float_and_rounds(value, expected):
    assert normalize_component(value) == expected


def test_normalize_component_rejects_negative():
    assert normalize_component(-1.2) is None


def test_normalize_component_does_not_convert_units():
    # OpenWeather already supplies these measurements in µg/m³.
    assert normalize_component(201.94) == 201.94


def test_normalize_components_normalizes_all_supported_fields():
    components = {
        "co": 201.941,
        "no": 0,
        "no2": "1.234",
        "o3": 68.678,
        "so2": 0.6,
        "pm2_5": 4.34,
        "pm10": 5.123,
        "nh3": 0.12,
    }

    result = normalize_components(components)

    assert result == {
        "co": 201.94,
        "no": 0.0,
        "no2": 1.23,
        "o3": 68.68,
        "so2": 0.6,
        "pm2_5": 4.34,
        "pm10": 5.12,
        "nh3": 0.12,
    }


def test_normalize_components_fills_missing_with_none():
    result = normalize_components({"co": 270.11})
    assert result["co"] == 270.11
    assert result["pm2_5"] is None
    assert set(result.keys()) == {
        "co", "no", "no2", "o3", "so2", "pm2_5", "pm10", "nh3"
    }

def test_normalize_components_sets_missing_fields_to_none():
    result = normalize_components({"co": 201.94})

    assert result["co"] == 201.94
    assert result["no"] is None
    assert result["no2"] is None
    assert result["o3"] is None
    assert result["so2"] is None
    assert result["pm2_5"] is None
    assert result["pm10"] is None
    assert result["nh3"] is None


def test_normalize_components_handles_none():
    result = normalize_components(None)

    assert all(value is None for value in result.values())


def test_normalize_components_negative_pollutant_becomes_none():
    result = normalize_components(
        {
            "co": -10,
            "pm2_5": 4.3,
        }
    )

    assert result["co"] is None
    assert result["pm2_5"] == 4.3


# --- Text normalization tests ---

@pytest.mark.parametrize(
    "value,expected",
    [
        (" San Francisco ", "San Francisco"),
        ("  US  ", "US"),
        (" California ", "California"),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_normalize_text_strips_whitespace_and_empty_values(
    value, expected
):
    assert normalize_text(value) == expected

def test_normalize_text_preserves_casing():
    assert normalize_text("San Francisco") == "San Francisco"
    assert normalize_text("san francisco") == "san francisco"


def test_normalize_text_preserves_non_ascii_characters():
    assert normalize_text(" Montréal ") == "Montréal"


# --- Normalize dedupe tests ---

def test_dedupe_records_keeps_highest_pipeline_run_id():
    records = [
        {"city_id": "city-1", "observed_at": "2024-07-03T10:00:00Z", "pipeline_run_id": "pipeline-2024-07-03-001", "aqi": 2},
        {"city_id": "city-1", "observed_at": "2024-07-03T10:00:00Z", "pipeline_run_id": "pipeline-2024-07-03-005", "aqi": 3},
        {"city_id": "city-1", "observed_at": "2024-12-05T10:00:00Z", "pipeline_run_id": "pipeline-2024-12-05-001", "aqi": 1},
    ]
    result = dedupe_records(
        records, key_fields=("city_id", "observed_at"), tiebreaker_field="pipeline_run_id"
    )
    assert len(result) == 2
    t1_record = next(r for r in result if r["observed_at"] == "2024-07-03T10:00:00Z")
    assert t1_record["aqi"] == 3

def test_dedupe_records_keeps_unique_observations():
    records = [
        {
            "city_id": "city-1",
            "observed_at": "2024-07-03T10:00:00Z",
            "pipeline_run_id": "pipeline-2024-07-03-001",
        },
        {
            "city_id": "city-1",
            "observed_at": "2024-07-03T11:00:00Z",
            "pipeline_run_id": "pipeline-2024-07-03-001",
        },
    ]

    result = dedupe_records(
        records,
        key_fields=("city_id", "observed_at"),
        tiebreaker_field="pipeline_run_id",
    )

    assert len(result) == 2


def test_dedupe_records_does_not_treat_different_cities_as_duplicates():
    records = [
        {
            "city_id": "city-1",
            "observed_at": "2024-07-03T10:00:00Z",
            "pipeline_run_id": "pipeline-2024-07-03-001",
        },
        {
            "city_id": "city-2",
            "observed_at": "2024-07-03T10:00:00Z",
            "pipeline_run_id": "pipeline-2024-07-03-001",
        },
    ]

    result = dedupe_records(
        records,
        key_fields=("city_id", "observed_at"),
        tiebreaker_field="pipeline_run_id",
    )

    assert len(result) == 2


def test_dedupe_records_keeps_highest_tiebreaker_value():
    records = [
        {
            "city_id": "city-1",
            "observed_at": "2024-07-03T10:00:00Z",
            "pipeline_run_id": "pipeline-2024-07-03-002",
        },
        {
            "city_id": "city-1",
            "observed_at": "2024-07-03T10:00:00Z",
            "pipeline_run_id": "pipeline-2024-07-03-005",
        },
        {
            "city_id": "city-1",
            "observed_at": "2024-07-03T10:00:00Z",
            "pipeline_run_id": "pipeline-2024-07-03-003",
        },
    ]

    result = dedupe_records(
        records,
        key_fields=("city_id", "observed_at"),
        tiebreaker_field="pipeline_run_id",
    )

    assert len(result) == 1
    assert result[0]["pipeline_run_id"] == "pipeline-2024-07-03-005"


def test_dedupe_records_preserves_first_seen_key_order():
    records = [
        {
            "city_id": "city-2",
            "observed_at": "2024-07-03T10:00:00Z",
            "pipeline_run_id": "pipeline-2024-07-03-001",
        },
        {
            "city_id": "city-1",
            "observed_at": "2024-07-03T10:00:00Z",
            "pipeline_run_id": "pipeline-2024-07-03-001",
        },
        {
            "city_id": "city-2",
            "observed_at": "2024-07-03T10:00:00Z",
            "pipeline_run_id": "pipeline-2024-07-03-002",
        },
    ]

    result = dedupe_records(
        records,
        key_fields=("city_id", "observed_at"),
        tiebreaker_field="pipeline_run_id",
    )

    assert [record["city_id"] for record in result] == [
        "city-2",
        "city-1",
    ]
    assert result[0]["pipeline_run_id"] == "pipeline-2024-07-03-002"


def test_dedupe_records_handles_missing_tiebreaker():
    records = [
        {
            "city_id": "city-1",
            "observed_at": "2024-07-03T10:00:00Z",
            "pipeline_run_id": None,
        },
        {
            "city_id": "city-1",
            "observed_at": "2024-07-03T10:00:00Z",
            "pipeline_run_id": "pipeline-2024-07-03-002",
        },
    ]

    result = dedupe_records(
        records,
        key_fields=("city_id", "observed_at"),
        tiebreaker_field="pipeline_run_id",
    )

    assert len(result) == 1
    assert result[0]["pipeline_run_id"] == "pipeline-2024-07-03-002"


# --- build_air_quality_record tests ---

@pytest.fixture
def _sample_observation():
    return {
        "dt": 1720000000,
        "main": {"aqi": 2},
        "components": {
            "co": 201.94, "no": 0.0, "no2": 1.2, "o3": 68.6,
            "so2": 0.6, "pm2_5": 4.3, "pm10": 5.1, "nh3": 0.12,
        },
    }

@pytest.fixture
def _sample_context():
    return {
        "city_id": "us-san-francisco-ca",
        "city_name": " San Francisco ",
        "country_code": "US",
        "state_code": "CA",
        "lat": 37.7749,
        "lon": -122.4194,
        "run_id": "run-2024-07-03-001",
        "pipeline_run_id": "pipeline-2024-07-03-001",
    }


def test_build_air_quality_record_maps_all_contract_fields(_sample_observation, _sample_context):
    record = build_air_quality_record(_sample_observation(), _sample_context())

    assert record["city_id"] == "us-san-francisco-ca"
    assert record["city_name"] == "San Francisco"  # normalize_text strips whitespace
    assert record["observed_at"] == datetime(2024, 7, 3, 9, 46, 40, tzinfo=timezone.utc)
    assert record["aqi"] == 2
    assert record["co"] == 201.94
    assert record["run_id"] == "run-2024-07-03-001"
    assert record["pipeline_run_id"] == "pipeline-2024-07-03-001"


def test_build_air_quality_record_omits_aqi_label_by_default(_sample_observation, _sample_context):
    record = build_air_quality_record(_sample_observation(), _sample_context())

    assert "aqi_label" not in record


def test_build_air_quality_record_includes_aqi_label_when_flagged(sample_observation, sample_context):
    record = build_air_quality_record(
        _sample_observation(), _sample_context(), include_aqi_label=True
    )

    assert record["aqi_label"] == "Fair"


def test_build_air_quality_record_drops_invalid_aqi_to_none(sample_observation, sample_context):
    observation = _sample_observation()
    observation["main"]["aqi"] = 99

    record = build_air_quality_record(observation, _sample_context())

    assert record["aqi"] is None
