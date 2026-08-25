from datetime import datetime, timezone

from .operations import (
    build_air_quality_record,
    dedupe_records,
    filter_valid_records,
)

def transform_raw_response(raw_response):
    """
    Transform one RawResponse envelope into a list of clean
    air-quality observation records.

    The function does not call the API or write to the database.
    It only converts the supplied raw response into the agreed
    clean record shape.

    One observation in payload["list"] becomes one output record.
    """

    # Response-level validation
    if not isinstance(raw_response, dict):
        raise ValueError("raw_response must be a dictionary")

    payload = raw_response.get("payload")

    if not isinstance(payload, dict):
        raise ValueError("RawResponse payload is missing or invalid")

    observations = payload.get("list")

    if observations is None:
        raise ValueError("RawResponse payload.list is missing")

    if not isinstance(observations, list):
        raise ValueError("RawResponse payload.list must be a list")

    # Empty response produces no records
    if not observations:
        return []

    # Build the context shared by all observations in this response.
    context = {
        "city_id": raw_response.get("city_id"),
        "city_name": raw_response.get("city_name"),
        "country_code": raw_response.get("country_code"),
        "state_code": raw_response.get("state_code"),
        "lat": raw_response.get("lat"),
        "lon": raw_response.get("lon"),
        "run_id": raw_response.get("run_id"),
        "pipeline_run_id": raw_response.get("pipeline_run_id"),
    }
    
    records = []

    for observation in observations:
        if not isinstance(observation, dict):
            continue

        # Required location/context fields
        record = build_air_quality_record(
            observation,
            context,
        )

         # Remove records that are missing required normalized fields.
    records = filter_valid_records(records)

    # Remove repeated observations using the agreed deduplication rule.
    #
    # IMPORTANT:
    # Use the tiebreaker field specified by the team's contract.
    records = dedupe_records(
        records,
        key_fields=("city_id", "observed_at"),
        tiebreaker_field="run_id",
    )

    return records