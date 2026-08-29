from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


# --- Rule: timestamp normalization ---

def unix_to_utc_datetime(dt_unix: Any) -> Optional[datetime]:
    """
    Convert an OpenWeather `dt` (Unix seconds) to a UTC datetime.
    None if missing/unparsable — observed_at is required, so caller drops the record.
    """
    if dt_unix is None:
        return None
    try:
        return datetime.fromtimestamp(int(dt_unix), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


# --- Rule: coordinate typing + range validation ---

def normalize_coordinate(value: Any, *, is_latitude: bool) -> Optional[float]:
    """
    Cast a coordinate to float and validate its range
    Latitude: -90..90, Longitude: -180..180.
    Returns None if missing, non-numeric, or out of range.

    This function re-validates defensively in case corrupted values ever reach the raw
    table by another path (manual insert, replay, etc.).
    """
    if value is None:
        return None
    try:
        coord = float(value)
    except (TypeError, ValueError):
        return None

    bound = 90.0 if is_latitude else 180.0
    if not (-bound <= coord <= bound):
        return None
    return coord


# --- Rule: AQI typing + meaningful label for the dashboard ---

_AQI_LABELS = {
    1: "Good",
    2: "Fair",
    3: "Moderate",
    4: "Poor",
    5: "Very Poor",
}

def normalize_aqi(value: Any) -> Optional[int]:
    """Cast OpenWeather's 1-5 AQI index to int; None if missing/out of range."""
    if value is None:
        return None
    try:
        aqi = int(value)
    except (TypeError, ValueError):
        return None
    return aqi if aqi in _AQI_LABELS else None


def aqi_label(aqi: Optional[int]) -> Optional[str]:
    """
    Map AQI (1-5) to its Human-readable AQI category (Good..Very Poor) display category;
    None if aqi is None.
    """
    if aqi is None:
        return None
    return _AQI_LABELS.get(aqi)


# --- Rule: pollutant concentration typing + validity (no unit conversion needed) ----

# All OpenWeather Air Pollution `components` values are already in ug/m3.
# No unit conversion is required. For only type-cast and reject physically-impossible (negative) readings.
COMPONENT_FIELDS = ("co", "no", "no2", "o3", "so2", "pm2_5", "pm10", "nh3")


def normalize_component(value: Any, *, decimals: int = 2) -> Optional[float]:
    """
    Cast a pollutant concentration to float and round it.
    Negative values are physically invalid and treated as missing (None), not dropped.
    """
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f < 0:
        return None
    return round(f, decimals)


def normalize_components(components: Optional[dict]) -> dict:
    """
    Normalize the full `components` object. Missing keys become None
    rather than raising, since individual pollutants are optional fields.
    """
    components = components or {}
    return {
        field: normalize_component(components.get(field))
        for field in COMPONENT_FIELDS
    }


# Rule: text normalization

def normalize_text(value: Any) -> Optional[str]:
    """
    Strip surrounding whitespace and collapse empty strings to None.

    Casing is preserved as returned by the API: city/country names can be
    non-ASCII (e.g., accented characters), and forcing title-case would
    corrupt some international names. city_id (not name) is the join key
    used elsewhere, so this is purely a display-field cleanup.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# Rule: duplicate / repeated records handling

def dedupe_records(
    records: list[dict],
    *,
    key_fields: tuple[str, ...],
    tiebreaker_field: str,
) -> list[dict]:
    """
    Remove duplicate records that share the same key_fields (city_id + observed_at),
    keeping the record with the highest tiebreaker_field value.
    Surviving records preserve first-seen order of each key.
    """
    best: dict[tuple, dict] = {}
    order: list[tuple] = []

    for record in records:
        key = tuple(record.get(f) for f in key_fields)
        if key not in best:
            order.append(key)
            best[key] = record
            continue
        current = best[key]
        candidate_tb = record.get(tiebreaker_field)
        current_tb = current.get(tiebreaker_field)
        if candidate_tb is not None and (current_tb is None or candidate_tb > current_tb):
            best[key] = record

    return [best[key] for key in order]


# --- Record assembly ---

def build_air_quality_record(
    observation: dict,
    context: dict,
) -> dict:
    """Build one AirQualityRecord from a raw observation and its RawResponse context."""

    aqi = normalize_aqi(observation.get("main", {}).get("aqi"))

    record = {
        "city_id": context.get("city_id"),
        "city_name": normalize_text(context.get("city_name")),
        "country_code": normalize_text(context.get("country_code")),
        "state_code": normalize_text(context.get("state_code")),
        "lat": normalize_coordinate(context.get("lat"), is_latitude=True),
        "lon": normalize_coordinate(context.get("lon"), is_latitude=False),
        "observed_at": unix_to_utc_datetime(observation.get("dt")),
        "aqi": aqi,
        "aqi_label": aqi_label(aqi),
        **normalize_components(observation.get("components")),
        "run_id": context.get("run_id"),
        "pipeline_run_id": context.get("pipeline_run_id"),
        "retrieved_at": context.get("retrieved_at"),
    }

    return record


# --- Rule: required-field enforcement ---

REQUIRED_FIELDS = ("city_id", "observed_at", "lat", "lon", "aqi", "retrieved_at")


def filter_valid_records(records: list[dict]) -> list[dict]:
    """
    Remove records missing any required normalized fields.
    Only records with non‑None values for city_id, observed_at, lat, lon, aqi, and retrieved_at are kept.
    Optional fields are not validated here.
    """
    return [
        record
        for record in records
        if all(record.get(field) is not None for field in REQUIRED_FIELDS)
    ]
