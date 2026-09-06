"""Integration tests for the cities reference-table upsert."""

from __future__ import annotations

import psycopg
from pipeline.extract.cities import City
from pipeline.load.cities import upsert_cities


def _count(conn: psycopg.Connection, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table};")
        (count,) = cur.fetchone()
    return count


def test_upsert_cities_inserts_new_cities(db_connection):
    cities = [
        City(
            city_id="us-austin-tx",
            city_name="Austin",
            country_code="US",
            state_code="TX",
            timezone="America/Chicago",
            active=True,
        ),
        City(
            city_id="us-denver-co",
            city_name="Denver",
            country_code="US",
            state_code="CO",
            timezone="America/Denver",
            active=True,
        ),
    ]

    count = upsert_cities(db_connection, cities)

    assert count == 2
    assert _count(db_connection, "cities") == 2


def test_upsert_cities_updates_existing_city_on_conflict(db_connection):
    city = City(
        city_id="us-austin-tx",
        city_name="Austin",
        country_code="US",
        state_code="TX",
        timezone="America/Chicago",
        active=True,
    )

    upsert_cities(db_connection, [city])

    updated = city.model_copy(update={"city_name": "Austin Metro", "active": False})
    upsert_cities(db_connection, [updated])

    assert _count(db_connection, "cities") == 1

    with db_connection.cursor() as cur:
        cur.execute(
            "SELECT city_name, active FROM cities WHERE city_id = %s;",
            (city.city_id,),
        )
        row = cur.fetchone()

    assert row == ("Austin Metro", False)


def test_upsert_cities_empty_list_is_a_noop(db_connection):
    assert upsert_cities(db_connection, []) == 0
    assert _count(db_connection, "cities") == 0
