"""Database upsert operations for the cities reference table."""

from __future__ import annotations

from collections.abc import Sequence

import psycopg

from pipeline.extract.cities import City

CITY_UPSERT_SQL = """
INSERT INTO cities (
    city_id,
    city_name,
    country_code,
    state_code,
    timezone,
    active
)
VALUES (
    %(city_id)s,
    %(city_name)s,
    %(country_code)s,
    %(state_code)s,
    %(timezone)s,
    %(active)s
)
ON CONFLICT (city_id)
DO UPDATE SET
    city_name = EXCLUDED.city_name,
    country_code = EXCLUDED.country_code,
    state_code = EXCLUDED.state_code,
    timezone = EXCLUDED.timezone,
    active = EXCLUDED.active;
"""


def upsert_cities(conn: psycopg.Connection, cities: Sequence[City]) -> int:
    """Insert or update the given cities in the `cities` reference table.

    Cities are static reference/dimension data, so the whole batch is upserted
    and committed as one unit ahead of any per-city raw/gold writes that FK to
    `cities.city_id`.
    """
    if not cities:
        return 0

    params = [
        {
            "city_id": city.city_id,
            "city_name": city.city_name,
            "country_code": city.country_code,
            "state_code": city.state_code,
            "timezone": city.timezone,
            "active": city.active,
        }
        for city in cities
    ]

    with conn.cursor() as cur:
        cur.executemany(CITY_UPSERT_SQL, params)

    conn.commit()
    return len(cities)
