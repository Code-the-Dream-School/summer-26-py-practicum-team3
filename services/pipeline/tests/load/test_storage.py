import psycopg
import pytest
from datetime import datetime, timezone

from pipeline.load.storage import save_transformed_records


@pytest.fixture
def conn():
    """Fresh DB connection + cleanup before each test."""
    connection = psycopg.connect("postgresql://localhost:5432/air_test_db")
    connection.autocommit = True

    with connection.cursor() as cur:
        cur.execute("DELETE FROM air_pollution_gold;")

    return connection


def test_save_transformed_records_success(conn):
    now = datetime.now(timezone.utc)

    records = [
        {
            "city_id": 303,
            "city_name": "San Diego",
            "country_code": "US",
            "state_code": "CA",
            "run_id": "run123",
            "pipeline_run_id": 1,
            "observed_at": now,
            "aqi": 42,
            "aqi_label": "Good",
            "pm2_5": 5.1,
            "pm10": 12.3,
            "co": 0.3,
            "no": 0.1,
            "no2": 0.2,
            "o3": 0.05,
            "so2": 0.01,
            "nh3": 0.02,
            "lat": 32.71,
            "lon": -117.16,
        }
    ]

    count = save_transformed_records(conn, records, retrieved_at=now)
    assert count == 1

    with conn.cursor() as cur:
        cur.execute(
            "SELECT city_id, aqi FROM air_pollution_gold WHERE city_id = %s",
            (303,),
        )
        row = cur.fetchone()

    assert row is not None
    assert row[0] == 303
    assert row[1] == 42


def test_save_transformed_records_empty(conn):
    count = save_transformed_records(conn, [], datetime.now(timezone.utc))
    assert count == 0


def test_save_transformed_records_missing_required(conn):
    records = [
        {
            "city_id": 303,
            # missing required fields like observed_at, aqi, etc.
        }
    ]

    with pytest.raises(ValueError):
        save_transformed_records(conn, records, datetime.now(timezone.utc))
