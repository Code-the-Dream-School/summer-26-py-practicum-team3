from __future__ import annotations

from typing import Any, Sequence
import psycopg
from psycopg.types.json import Jsonb


RAW_GEOCODING_SQL = """
    INSERT INTO raw_geocoding_responses (
        pipeline_run_id,
        city_id,
        city_name,
        country_code,
        state_code,
        lat,
        lon,
        coordinate_source,
        endpoint,
        retrieved_at,
        http_status,
        payload
    )
    VALUES (
        %(pipeline_run_id)s,
        %(city_id)s,
        %(city_name)s,
        %(country_code)s,
        %(state_code)s,
        %(lat)s,
        %(lon)s,
        %(coordinate_source)s,
        %(endpoint)s,
        %(retrieved_at)s,
        %(http_status)s,
        %(payload)s
    )
    RETURNING raw_geocoding_response_id;
"""


RAW_AIR_POLLUTION_SQL = """
    INSERT INTO raw_air_pollution_responses (
        pipeline_run_id,
        city_id,
        city_name,
        country_code,
        state_code,
        lat,
        lon,
        start,
        "end",
        endpoint,
        retrieved_at,
        http_status,
        payload
    )
    VALUES (
        %(pipeline_run_id)s,
        %(city_id)s,
        %(city_name)s,
        %(country_code)s,
        %(state_code)s,
        %(lat)s,
        %(lon)s,
        %(start)s,
        %(end)s,
        %(endpoint)s,
        %(retrieved_at)s,
        %(http_status)s,
        %(payload)s
    )
    RETURNING raw_air_pollution_response_id;
"""

LOAD_RAW_AIR_POLLUTION_SQL = """
    SELECT city_id, city_name, country_code, state_code, lat, lon, retrieved_at, payload
    FROM raw_air_pollution_responses
    WHERE pipeline_run_id = %s
    ORDER BY raw_air_pollution_response_id;
"""

RAW_GEOCODING_REQUIRED = (
    "pipeline_run_id", "city_id", "city_name", "country_code",
    "endpoint", "retrieved_at", "http_status", "payload",
)

RAW_AIR_REQUIRED = (
    "pipeline_run_id", "city_id", "city_name", "country_code", "coordinate_source",
    "lat", "lon", "endpoint", "retrieved_at", "http_status", "payload",
)


def _validate_required_fields(record: dict[str, Any], required: Sequence[str]) -> None:
    """
    Ensure all required fields are present and non‑None before INSERT.
    Raises ValueError if the record is incomplete.
    """
    missing = [f for f in required if f not in record or record[f] is None]

    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def save_raw_geocoding_response(
    conn: psycopg.Connection,
    record: dict[str, Any],
) -> int:
    """
    Insert one raw geocoding response. Returns the new row id.
    Expects a dict already shaped to the raw schema.
    """
    _validate_required_fields(record, RAW_GEOCODING_REQUIRED)

    params = {
        "pipeline_run_id": record["pipeline_run_id"],
        "city_id": record["city_id"],
        "city_name": record["city_name"],
        "country_code": record["country_code"],
        "state_code": record.get("state_code"),
        "lat": record.get("lat"),
        "lon": record.get("lon"),
        "coordinate_source": record.get("coordinate_source"),
        "endpoint": record["endpoint"],
        "retrieved_at": record["retrieved_at"],
        "http_status": record["http_status"],
        "payload": Jsonb(record["payload"]),
    }

    with conn.cursor() as cur:
        cur.execute(RAW_GEOCODING_SQL, params)
        row = cur.fetchone()

    conn.commit()
    return row[0]


def save_raw_air_pollution_response(
    conn: psycopg.Connection,
    record: dict[str, Any],
) -> int:
    """
    Insert one raw air pollution response. Returns the new row id.
    Expects a dict matching the raw air‑pollution schema.
    """
    _validate_required_fields(record, RAW_AIR_REQUIRED )

    params = {
        "pipeline_run_id": record["pipeline_run_id"],
        "city_id": record["city_id"],
        "city_name": record["city_name"],
        "country_code": record["country_code"],
        "state_code": record.get("state_code"),
        "lat": record["lat"],
        "lon": record["lon"],
        "start": record.get("start"),
        "end": record.get("end"),
        "endpoint": record["endpoint"],
        "retrieved_at": record["retrieved_at"],
        "http_status": record["http_status"],
        "payload": Jsonb(record["payload"]),
    }

    with conn.cursor() as cur:
        cur.execute(RAW_AIR_POLLUTION_SQL, params)
        row = cur.fetchone()

    conn.commit()
    return row[0]


def load_raw_air_pollution_responses(
    conn: psycopg.Connection,
    source_pipeline_run_id: int,
    run_id: str,
    pipeline_run_id: int,
) -> list[dict[str, Any]]:
    """Reconstruct transform-input envelopes from previously persisted raw responses.

    Used to replay transform without calling the API again. `run_id`/`pipeline_run_id` are the
    *new* (replay) run's values, not the original run's — each returned envelope is tagged with
    them so the resulting gold rows are correctly attributed to this replay.
    """
    with conn.cursor() as cur:
        cur.execute(LOAD_RAW_AIR_POLLUTION_SQL, (source_pipeline_run_id,))
        rows = cur.fetchall()

    envelopes: list[dict[str, Any]] = []
    for city_id, city_name, country_code, state_code, lat, lon, retrieved_at, payload in rows:
        status = "empty" if not payload.get("list") else "ok"
        envelopes.append(
            {
                "status": status,
                "payload": payload,
                "city_id": city_id,
                "city_name": city_name,
                "country_code": country_code,
                "state_code": state_code,
                "lat": lat,
                "lon": lon,
                "retrieved_at": retrieved_at,
                "run_id": run_id,
                "pipeline_run_id": pipeline_run_id,
            }
        )

    return envelopes
