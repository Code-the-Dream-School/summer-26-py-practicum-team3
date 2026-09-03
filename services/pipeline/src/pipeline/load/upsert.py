"""Database upsert operations for Gold air pollution records."""

from __future__ import annotations

from typing import Any, Sequence

AIR_QUALITY_UPSERT_SQL = """
INSERT INTO air_pollution_gold (
    city_id,
    observed_at,
    city_name,
    country_code,
    state_code,
    lat,
    lon,
    aqi,
    aqi_label,
    co,
    no2,
    no,
    o3,
    so2,
    pm2_5,
    pm10,
    nh3,
    run_id,
    pipeline_run_id,
    retrieved_at
)
VALUES (
    %(city_id)s,
    %(observed_at)s,
    %(city_name)s,
    %(country_code)s,
    %(state_code)s,
    %(lat)s,
    %(lon)s,
    %(aqi)s,
    %(aqi_label)s,
    %(co)s,
    %(no2)s,
    %(no)s,
    %(o3)s,
    %(so2)s,
    %(pm2_5)s,
    %(pm10)s,
    %(nh3)s,
    %(run_id)s,
    %(pipeline_run_id)s,
    %(retrieved_at)s
)
ON CONFLICT (city_id, observed_at)
DO UPDATE SET
    city_name = EXCLUDED.city_name,
    country_code = EXCLUDED.country_code,
    state_code = EXCLUDED.state_code,
    lat = EXCLUDED.lat,
    lon = EXCLUDED.lon,
    aqi = EXCLUDED.aqi,
    aqi_label = EXCLUDED.aqi_label,
    co = EXCLUDED.co,
    no2 = EXCLUDED.no2,
    no = EXCLUDED.no,
    o3 = EXCLUDED.o3,
    so2 = EXCLUDED.so2,
    pm2_5 = EXCLUDED.pm2_5,
    pm10 = EXCLUDED.pm10,
    nh3 = EXCLUDED.nh3,
    run_id = EXCLUDED.run_id,
    pipeline_run_id = EXCLUDED.pipeline_run_id,
    retrieved_at = EXCLUDED.retrieved_at
WHERE EXCLUDED.pipeline_run_id > air_pollution_gold.pipeline_run_id;
"""


def upsert_air_quality_record(cursor: Any, record: dict[str, Any]) -> None:
    """Insert a new air-quality record or update an existing observation.

    Records are uniquely identified by (city_id, observed_at).
    Updates only occur if the incoming record has a higher pipeline_run_id.
    """
    if not record:
        return 0
    cursor.execute(AIR_QUALITY_UPSERT_SQL, record)
    return cursor.rowcount


def upsert_air_quality_records(cursor: Any, records: Sequence[dict[str, Any]]) -> int:
    """Insert or update a collection of air-quality records."""
    count = 0
    for record in records:
        if record:
            count += upsert_air_quality_record(cursor, record)
    return count