""" test load/ - insert, raw, gold response, transformed record, upsert """

from datetime import datetime, timezone

import psycopg

import pytest

from pipeline.load.raw import (
    save_raw_geocoding_response,
    save_raw_air_pollution_response,
)
from pipeline.load.gold import save_transformed_records
from pipeline.load.upsert import upsert_air_quality_record


# Helper for counting rows in a database table
def _count(conn: psycopg.Connection, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table};")
        (count,) = cur.fetchone()
    return count


def test_sanity_insert(db_connection, seeded_city_and_run):
    """Sanity test: fixture inserts city + pipeline_run correctly."""
    city_id, pipeline_run_id = seeded_city_and_run

    # Verify city exists
    with db_connection.cursor() as cur:
        cur.execute("SELECT city_name FROM cities WHERE city_id = %s;", (city_id,))
        row = cur.fetchone()
    assert row == ("Los Angeles",)

    # Verify pipeline_run exists
    with db_connection.cursor() as cur:
        cur.execute(
            "SELECT run_id FROM pipeline_runs WHERE pipeline_run_id = %s;",
            (pipeline_run_id,),
        )
        row = cur.fetchone()

    assert row == ("test-run-1",)


def test_write_new_raw_and_gold(db_connection, seeded_city_and_run):
    """Writing a new raw response and a new transformed record succeeds."""
    city_id, pipeline_run_id = seeded_city_and_run
    now = datetime.now(timezone.utc)

    # Raw geocoding
    save_raw_geocoding_response(
        db_connection,
        {
            "pipeline_run_id": pipeline_run_id,
            "city_id": city_id,
            "city_name": "Los Angeles",
            "country_code": "US",
            "state_code": "CA",
            "lat": 34.0522,
            "lon": -118.2437,
            "coordinate_source": "geocoded",
            "endpoint": "/geo",
            "retrieved_at": now,
            "http_status": 200,
            "payload": {"raw": "geo"}
        },
    )

    # Raw air pollution
    save_raw_air_pollution_response(
        db_connection,
            {
                "pipeline_run_id": pipeline_run_id,
                "city_id": city_id,
                "city_name": "Los Angeles",
                "country_code": "US",
                "state_code": "CA",
                "lat": 34.0522,
                "lon": -118.2437,
                "start": now,
                "end": now,
                "coordinate_source": "geocoded",
                "endpoint": "/air",
                "retrieved_at": now,
                "http_status": 200,
                "payload": {"raw": "air"},
            },
    )

    # Gold record
    save_transformed_records(
        db_connection,
        [
            {
                "city_id": city_id,
                "city_name": "Los Angeles",
                "country_code": "US",
                "state_code": "CA",
                "run_id": "run-1",
                "pipeline_run_id": pipeline_run_id,
                "observed_at": now,
                "aqi": 3,
                "aqi_label": "Moderate",
                "pm2_5": 10.0,
                "pm10": 20.0,
                "co": 0.5,
                "no": 0.1,
                "no2": 0.2,
                "o3": 0.3,
                "so2": 0.4,
                "nh3": 0.5,
                "lat": 34.0522,
                "lon": -118.2437,
                "retrieved_at": now,
            }
        ],
        retrieved_at=now,
    )

    assert _count(db_connection, "raw_geocoding_responses") == 1
    assert _count(db_connection, "raw_air_pollution_responses") == 1
    assert _count(db_connection, "air_pollution_gold") == 1


def test_upsert_no_duplicates(db_connection, seeded_city_and_run):
    """Upsert with identical input does not create duplicate gold records."""
    city_id, pipeline_run_id = seeded_city_and_run
    observed_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    cur = db_connection.cursor()

    record = {
        "city_id": city_id,
        "city_name": "Los Angeles",
        "country_code": "US",
        "state_code": "CA",
        "run_id": "run1",
        "pipeline_run_id": pipeline_run_id,
        "observed_at": observed_at,
        "aqi": 2,
        "aqi_label": "Fair",
        "lat": 34.0522,
        "lon": -118.2437,
        "co": 0.5,
        "no2": 0.2,
        "no": 0.1,
        "o3": 0.3,
        "so2": 0.4,
        "pm2_5": 10.0,
        "pm10": 20.0,
        "nh3": 0.5,
        "retrieved_at": now,
    }

    upsert_air_quality_record(cur, record)
    upsert_air_quality_record(cur, record)

    assert _count(db_connection, "air_pollution_gold") == 1


def test_upsert_updates_existing_values(db_connection, seeded_city_and_run):
    """Upsert with modified values updates the existing gold record."""
    city_id, pipeline_run_id = seeded_city_and_run
    observed_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    cur = db_connection.cursor()

    original = {
        "city_id": city_id,
        "city_name": "Los Angeles",
        "country_code": "US",
        "state_code": "CA",
        "run_id": "run1",
        "observed_at": observed_at,
        "aqi": 2,
        "aqi_label": "Fair",
        "lat": 34.0522,
        "lon": -118.2437,
        "co": 0.5,
        "no2": 0.2,
        "no": 0.1,
        "o3": 0.3,
        "so2": 0.4,
        "pm2_5": 10.0,
        "pm10": 20.0,
        "nh3": 0.5,
        "pipeline_run_id": pipeline_run_id,
        "retrieved_at": now,
    }

    updated = {**original, "aqi": 4, "aqi_label": "Poor", "pm2_5": 30.0,}

    upsert_air_quality_record(cur, original)
    upsert_air_quality_record(cur, updated)

    assert _count(db_connection, "air_pollution_gold") == 1

    with db_connection.cursor() as cur:
        cur.execute(
            """
            SELECT aqi, aqi_label, pm2_5
            FROM air_pollution_gold
            WHERE city_id = %s AND observed_at = %s;
            """,
            (city_id, observed_at),
        )
        row = cur.fetchone()

    assert row == (4, "Poor", 30.0)


def test_empty_input(db_connection):
    """Empty or missing input is handled gracefully."""
    cur = db_connection.cursor()

    # save_transformed_records should return 0 for empty list
    assert save_transformed_records(cur, [], datetime.now(timezone.utc)) == 0

    # upsert should ignore None input
    upsert_air_quality_record(cur, None)

    # invalid input should raise
    with pytest.raises(TypeError):
        upsert_air_quality_record(cur, {"city_id": None})


def test_empty_and_missing_input_behaviour(db_connection: psycopg.Connection, seeded_city_and_run: tuple[str, int]) -> None:
    """empty/missing input handling for gold and upsert."""
    city_id, pipeline_run_id = seeded_city_and_run
    now = datetime.now(timezone.utc)

    # empty list → save_transformed_records returns 0 and writes nothing
    inserted = save_transformed_records(db_connection, [], retrieved_at=now)
    assert inserted == 0
    assert _count(db_connection, "air_pollution_gold") == 0

    # None record → upsert_air_quality_record writes nothing
    with db_connection.cursor() as cur:
        upsert_air_quality_record(cur, None)

    assert _count(db_connection, "air_pollution_gold") == 0

    # missing required field → ValueError and table stays empty
    bad_record = {
        # "city_id" missing
        "city_name": "Los Angeles",
        "country_code": "US",
        "state_code": "CA",
        "lat": 34.0522,
        "lon": -118.2437,
        "observed_at": now,
        "aqi": 3,
        "aqi_label": "Moderate",
        "co": 0.5,
        "no2": 0.2,
        "no": 0.1,
        "o3": 0.3,
        "so2": 0.4,
        "pm2_5": 10.0,
        "pm10": 20.0,
        "nh3": 0.5,
        "run_id": "run-1",
        "pipeline_run_id": pipeline_run_id,
        "retrieved_at": now,
    }

    with db_connection.cursor() as cur:
        with pytest.raises(TypeError):
            upsert_air_quality_record(cur, bad_record)

    assert _count(db_connection, "air_pollution_gold") == 0
