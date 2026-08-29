import psycopg
import pytest
from datetime import datetime, timezone

from pipeline.load.raw import (
    save_raw_geocoding_response,
    save_raw_air_pollution_response,
)


# --- Raw geocoding tests ---

def test_save_raw_geocoding_response_success(conn):
    record = {
        "pipeline_run_id": 1,
        "city_id": 101,
        "city_name": "Sacramento",
        "country_code": "US",
        "state_code": "CA",
        "lat": 38.58,
        "lon": -121.49,
        "coordinate_source": "api",
        "endpoint": "geocoding",
        "retrieved_at": datetime.now(timezone.utc),
        "http_status": 200,
        "payload": {"ok": True},
    }

    new_id = save_raw_geocoding_response(conn, record)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT city_id, city_name FROM raw_geocoding_responses WHERE raw_geocoding_response_id = %s",
            (new_id,),
        )
        row = cur.fetchone()

    assert row is not None
    assert row[0] == 101
    assert row[1] == "Sacramento"


def test_save_raw_geocoding_missing_required(conn):
    record = {
        "city_id": 101,
        # missing required fields
    }

    with pytest.raises(ValueError):
        save_raw_geocoding_response(conn, record)


# --- Raw air pollution tests ---

def test_save_raw_air_pollution_response_success(conn):
    record = {
        "pipeline_run_id": 1,
        "city_id": 202,
        "city_name": "Los Angeles",
        "country_code": "US",
        "state_code": "CA",
        "lat": 34.05,
        "lon": -118.24,
        "coordinate_source": "api",
        "endpoint": "air_pollution",
        "retrieved_at": datetime.now(timezone.utc),
        "http_status": 200,
        "payload": {"ok": True},
        "start": None,
        "end": None,
    }

    new_id = save_raw_air_pollution_response(conn, record)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT city_id, city_name FROM raw_air_pollution_responses WHERE raw_air_pollution_response_id = %s",
            (new_id,),
        )
        row = cur.fetchone()

    assert row is not None
    assert row[0] == 202
    assert row[1] == "Los Angeles"


def test_save_raw_air_pollution_missing_required(conn):
    record = {
        "city_id": 202,
        # missing required fields
    }

    with pytest.raises(ValueError):
        save_raw_air_pollution_response(conn, record)
