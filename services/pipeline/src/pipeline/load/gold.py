"""Gold table persistence helpers delegating to atomic upsert."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import psycopg

from pipeline.load.upsert import upsert_air_quality_records

# Pollutants and state_code are excluded, since they are optional.
GOLD_REQUIRED = (
    "city_id", "city_name", "country_code", "run_id", "pipeline_run_id",
    "observed_at", "aqi", "lat", "lon", "retrieved_at"
)


def _validate_required_fields(record: dict[str, Any], required: Sequence[str]) -> None:
    """
    Ensure all required fields are present and non-None before INSERT/UPSERT.
    Raises ValueError if the record is incomplete.
    """
    missing = [f for f in required if f not in record or record[f] is None]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def save_transformed_records(
    conn: psycopg.Connection,
    records: Sequence[dict[str, Any]],
) -> int:
    """Saves transformed gold records using the canonical upsert strategy."""
    if not records:
        return 0

    enriched_records: list[dict[str, Any]] = []
    
    for r in records:
        # Explicitly build a dict with every key AIR_QUALITY_UPSERT_SQL expects.
        # This protects psycopg from a KeyError if the source dict is missing a key entirely.   
        row = {
            "city_id": r.get("city_id"),
            "city_name": r.get("city_name"),
            "country_code": r.get("country_code"),
            "state_code": r.get("state_code"),
            "run_id": r.get("run_id"),
            "pipeline_run_id": r.get("pipeline_run_id"),
            "observed_at": r.get("observed_at"),
            "aqi": r.get("aqi"),
            "aqi_label": r.get("aqi_label"),
            "pm2_5": r.get("pm2_5"),
            "pm10": r.get("pm10"),
            "co": r.get("co"),
            "no": r.get("no"),
            "no2": r.get("no2"),
            "o3": r.get("o3"),
            "so2": r.get("so2"),
            "nh3": r.get("nh3"),
            "lat": r.get("lat"),
            "lon": r.get("lon"),
            "retrieved_at": r.get("retrieved_at"),
        }
        
        _validate_required_fields(row, GOLD_REQUIRED)
        enriched_records.append(row)

    with conn.cursor() as cur:
        count = upsert_air_quality_records(cur, enriched_records)

    conn.commit()
    return count