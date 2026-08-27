from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

import psycopg


GOLD_INSERT_SQL = """
    INSERT INTO air_pollution_gold (
        city_id,
        city_name,
        country_code,
        state_code,
        run_id,
        pipeline_run_id,
        observed_at,
        aqi,
        aqi_label,
        pm2_5,
        pm10,
        co,
        no,
        no2,
        o3,
        so2,
        nh3,
        lat,
        lon,
        retrieved_at
    )
    VALUES (
        %(city_id)s,
        %(city_name)s,
        %(country_code)s,
        %(state_code)s,
        %(run_id)s,
        %(pipeline_run_id)s,
        %(observed_at)s,
        %(aqi)s,
        %(aqi_label)s,
        %(pm2_5)s,
        %(pm10)s,
        %(co)s,
        %(no)s,
        %(no2)s,
        %(o3)s,
        %(so2)s,
        %(nh3)s,
        %(lat)s,
        %(lon)s,
        %(retrieved_at)s
    );
"""


GOLD_REQUIRED = (
    "city_id", "city_name", "country_code", "run_id", "pipeline_run_id",
    "observed_at",
    "aqi", "aqi_label", "pm2_5", "pm10", "co", "no", "no2", "o3", "so2", "nh3",
    "lat", "lon",
)


def _validate_required_fields(record: dict[str, Any], required: Sequence[str]) -> None:
    """
    Ensure all required fields are present and non‑None before INSERT.
    Raises ValueError if the record is incomplete.
    """
    missing = [f for f in required if f not in record or record[f] is None]

    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def save_transformed_records(
    conn: psycopg.Connection,
    records: Sequence[dict[str, Any]],
    retrieved_at: datetime,
) -> int:
    """
    Insert transformed Sprint 3 gold records.
    Expects fully‑shaped records and returns the number inserted.
    """
    if not records:
        return 0

    for r in records:
        _validate_required_fields(r, GOLD_REQUIRED )

    rows = [
        {
            "city_id": r["city_id"],
            "city_name": r["city_name"],
            "country_code": r["country_code"],
            "state_code": r.get("state_code"),
            "run_id": r["run_id"],
            "pipeline_run_id": r["pipeline_run_id"],
            "observed_at": r["observed_at"],
            "aqi": r["aqi"],
            "aqi_label": r["aqi_label"],
            "pm2_5": r["pm2_5"],
            "pm10": r["pm10"],
            "co": r["co"],
            "no": r["no"],
            "no2": r["no2"],
            "o3": r["o3"],
            "so2": r["so2"],
            "nh3": r["nh3"],
            "lat": r["lat"],
            "lon": r["lon"],
            "retrieved_at": retrieved_at,
        }
        for r in records
    ]

    with conn.cursor() as cur:
        cur.executemany(GOLD_INSERT_SQL, rows)

    conn.commit()
    return len(rows)
