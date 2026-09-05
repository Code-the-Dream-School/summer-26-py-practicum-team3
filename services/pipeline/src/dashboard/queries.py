"""Database query functions powering Streamlit dashboard views."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg


def _execute_and_fetch(
    conn: psycopg.Connection[dict[str, Any]],
    query: str,
    params: dict[str, Any] | tuple[Any, ...] | None = None,
) -> list[dict[str, Any]]:
    """Execute a query safely, handle database errors with rollback, and fetch results."""
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return list(cur.fetchall())
    except psycopg.Error:
        conn.rollback()
        raise


def list_cities(conn: psycopg.Connection[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fetch all active configured cities sorted alphabetically.

    Args:
        conn: Open database connection.

    Returns:
        List of dictionaries with city identifiers and metadata (active cities only).
    """
    query = """
        SELECT
            city_id,
            city_name,
            country_code,
            state_code
        FROM cities
        WHERE active = true
        ORDER BY city_name ASC;
    """
    return _execute_and_fetch(conn, query)


def get_latest_readings(conn: psycopg.Connection[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fetch the single most recent air pollution observation for each active city.

    Args:
        conn: Open database connection.

    Returns:
        List of dictionaries containing latest pollutant and AQI values per active city.
    """
    query = """
        WITH ranked_readings AS (
            SELECT
                g.city_id,
                c.city_name,
                c.country_code,
                c.state_code,
                g.observed_at,
                g.aqi,
                g.aqi_label,
                g.co,
                g.no,
                g.no2,
                g.o3,
                g.so2,
                g.pm2_5,
                g.pm10,
                g.nh3,
                ROW_NUMBER() OVER (
                    PARTITION BY g.city_id
                    ORDER BY g.observed_at DESC
                ) AS rn
            FROM air_pollution_gold AS g
            JOIN cities AS c ON g.city_id = c.city_id AND c.active = true
        )
        SELECT
            city_id,
            city_name,
            country_code,
            state_code,
            observed_at,
            aqi,
            aqi_label,
            co,
            no,
            no2,
            o3,
            so2,
            pm2_5,
            pm10,
            nh3
        FROM ranked_readings
        WHERE rn = 1
        ORDER BY city_name ASC;
    """
    return _execute_and_fetch(conn, query)

def get_city_history(
    conn: psycopg.Connection[dict[str, Any]],
    city_id: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Fetch historical air pollution time series for a specific active city.

    Args:
        conn: Open database connection.
        city_id: Target string city identifier (e.g. 'berlin-de').
        start: Inclusive window start timestamp, must be timezone-aware.
        end: Inclusive window end timestamp, must be timezone-aware.

    Returns:
        Chronologically sorted list of observed pollution measurements.
    """
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end datetimes must be timezone-aware.")

    query = """
        SELECT
            g.city_id,
            c.city_name,
            c.country_code,
            c.state_code,
            g.observed_at,
            g.aqi,
            g.co,
            g.no,
            g.no2,
            g.o3,
            g.so2,
            g.pm2_5,
            g.pm10,
            g.nh3
        FROM air_pollution_gold AS g
        JOIN cities AS c ON g.city_id = c.city_id AND c.active = true
        WHERE g.city_id = %(city_id)s
          AND g.observed_at >= %(start)s
          AND g.observed_at <= %(end)s
        ORDER BY g.observed_at ASC;
    """
    params = {
        "city_id": city_id,
        "start": start,
        "end": end,
    }
    return _execute_and_fetch(conn, query, params)


def get_cities_comparison(
    conn: psycopg.Connection[dict[str, Any]],
    city_ids: list[str],
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Fetch air pollution time series for multiple active cities within a time window.

    Args:
        conn: Open database connection.
        city_ids: List of target string city identifiers (e.g. ['berlin-de', 'london-gb']).
        start: Inclusive window start timestamp, must be timezone-aware.
        end: Inclusive window end timestamp, must be timezone-aware.

    Returns:
        List of observations across all selected cities sorted by city and timestamp.
    """
    if not city_ids:
        return []

    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end datetimes must be timezone-aware.")

    query = """
        SELECT
            g.city_id,
            c.city_name,
            c.country_code,
            c.state_code,
            g.observed_at,
            g.aqi,
            g.co,
            g.no,
            g.no2,
            g.o3,
            g.so2,
            g.pm2_5,
            g.pm10,
            g.nh3
        FROM air_pollution_gold AS g
        JOIN cities AS c ON g.city_id = c.city_id AND c.active = true
        WHERE g.city_id = ANY(%(city_ids)s)
          AND g.observed_at >= %(start)s
          AND g.observed_at <= %(end)s
        ORDER BY c.city_name ASC, g.observed_at ASC;
    """
    params = {
        "city_ids": city_ids,
        "start": start,
        "end": end,
    }
    return _execute_and_fetch(conn, query, params)