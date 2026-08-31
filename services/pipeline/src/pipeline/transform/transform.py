from __future__ import annotations

from .operations import (
    build_air_quality_record,
    dedupe_records,
    filter_valid_records,
)


def transform_raw_response(raw_response: dict) -> list[dict]:
    """
    Transform one RawResponse envelope into a list of clean
    air-quality observation records.
    """
    if not isinstance(raw_response, dict):
        raise ValueError("raw_response must be a dictionary")

    status = raw_response.get("status")

    if status in ("empty", "error"):
        return []

    if status != "ok":
        raise ValueError(f"Invalid RawResponse status: {status!r}")

    payload = raw_response.get("payload")

    if not isinstance(payload, dict):
        raise ValueError("RawResponse payload is missing or invalid")

    observations = payload.get("list")

    if observations is None:
        raise ValueError("RawResponse payload.list is missing")

    if not isinstance(observations, list):
        raise ValueError("RawResponse payload.list must be a list")

    if not observations:
        return []

    context = {
        "city_id": raw_response.get("city_id"),
        "city_name": raw_response.get("city_name"),
        "country_code": raw_response.get("country_code"),
        "state_code": raw_response.get("state_code"),
        "lat": raw_response.get("lat"),
        "lon": raw_response.get("lon"),
        "retrieved_at": raw_response.get("retrieved_at"),
        "run_id": raw_response.get("run_id"),
        "pipeline_run_id": raw_response.get("pipeline_run_id"),
    }

    records = []

    for observation in observations:
        if not isinstance(observation, dict):
            continue

        record = build_air_quality_record(
            observation,
            context,
        )
        records.append(record)

    records = filter_valid_records(records)

    records = dedupe_records(
        records,
        key_fields=("city_id", "observed_at"),
        tiebreaker_field="pipeline_run_id",
    )

    return records