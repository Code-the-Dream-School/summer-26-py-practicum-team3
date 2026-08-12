"""OpenWeather Historical Air Pollution API extract client.

Provides functionality for fetching historical air pollution raw data
and persisting unparsed raw API responses to disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

# NOTE: The 'pipeline.common.*' modules do not exist in 'main' yet.
# Importing this module directly will raise ModuleNotFoundError until the common package is merged.
from pipeline.common.config import settings
from pipeline.common.logging import get_logger

log = get_logger(__name__)

OPENWEATHER_HISTORY_URL = (
    "https://api.openweathermap.org/data/2.5/air_pollution/history"
)


class OpenWeatherRequestError(RuntimeError):
    """Raised internally when the API call fails or the response is unusable."""

    pass


@dataclass(frozen=True)
class RawAirPollutionRecord:
    city: str
    country_code: str
    lat: float
    lon: float
    start: datetime
    end: datetime
    run_id: str
    pipeline_run_id: int
    status: str
    raw_response: dict[str, Any] | None = None
    error_message: str | None = None


def fetch_air_pollution_history(
    raw_dir: Path | None,
    city: str,
    country_code: str,
    lat: float,
    lon: float,
    start: datetime,
    end: datetime,
    run_id: str,
    pipeline_run_id: int,
    api_key: str | None = None,
    http_client: Any = None,
) -> RawAirPollutionRecord:
    """Fetch historical air pollution data from OpenWeather API for a given location and window."""
    _validate_location(lat, lon)
    _validate_window(start, end)

    if api_key is None:
        # Extract secret value if wrapped in SecretStr to prevent passing masked values ('**********') to the API
        api_key = (
            settings.openweather_api_key.get_secret_value()
            if hasattr(settings.openweather_api_key, "get_secret_value")
            else str(settings.openweather_api_key)
        )

    client = http_client or requests

    try:
        payload = _request_history(
            lat=lat,
            lon=lon,
            start=start,
            end=end,
            api_key=api_key,
            http_client=client,
            raw_dir=raw_dir,
            city=city,
            country_code=country_code,
            run_id=run_id,
        )
    except OpenWeatherRequestError as exc:
        log.warning(
            "Failed to fetch air pollution data for %s, %s: %s",
            city,
            country_code,
            exc,
            extra={
                "run_id": run_id,
                "pipeline_run_id": pipeline_run_id,
                "city": city,
            },
        )
        return RawAirPollutionRecord(
            city=city,
            country_code=country_code,
            lat=lat,
            lon=lon,
            start=start,
            end=end,
            run_id=run_id,
            pipeline_run_id=pipeline_run_id,
            status="error",
            raw_response=None,
            error_message=str(exc),
        )

    entries = payload.get("list", [])

    # An empty 'list' field in a 200 OK response indicates no recorded measurements for the period,
    # distinguishing missing data ("empty") from network/API execution failures ("error").
    status = "ok" if entries else "empty"

    return RawAirPollutionRecord(
        city=city,
        country_code=country_code,
        lat=lat,
        lon=lon,
        start=start,
        end=end,
        run_id=run_id,
        pipeline_run_id=pipeline_run_id,
        status=status,
        raw_response=payload,
    )


def _validate_location(lat: float, lon: float) -> None:
    if lat < -90 or lat > 90:
        raise ValueError(f"lat must be between -90 and 90, got {lat!r}")
    if lon < -180 or lon > 180:
        raise ValueError(f"lon must be between -180 and 180, got {lon!r}")


def _validate_window(start: datetime, end: datetime) -> None:
    if start.tzinfo is None:
        raise ValueError("start must be timezone-aware")
    if end.tzinfo is None:
        raise ValueError("end must be timezone-aware")
    if start >= end:
        raise ValueError(f"start ({start}) must be before end ({end})")


def _request_history(
    lat: float,
    lon: float,
    start: datetime,
    end: datetime,
    api_key: str,
    http_client: Any,
    raw_dir: Path | None,
    city: str,
    country_code: str,
    run_id: str,
) -> dict[str, Any]:
    params = {
        "lat": lat,
        "lon": lon,
        "start": int(start.timestamp()),
        "end": int(end.timestamp()),
        "appid": api_key,
    }

    try:
        response = http_client.get(
            OPENWEATHER_HISTORY_URL, params=params, timeout=10
        )
    except requests.RequestException as exc:
        raise OpenWeatherRequestError(f"Request to OpenWeather failed: {exc}") from exc

    # Save exact response text prior to validation and JSON parsing to preserve an unedited audit trail
    _save_raw_response(
        raw_dir=raw_dir,
        city=city,
        country_code=country_code,
        run_id=run_id,
        raw_text=response.text,
    )

    if response.status_code != 200:
        raise OpenWeatherRequestError(
            f"OpenWeather returned status {response.status_code}: {response.text[:500]}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise OpenWeatherRequestError(
            f"Invalid JSON response from OpenWeather: {exc}"
        ) from exc


def _save_raw_response(
    raw_dir: Path | None,
    city: str,
    country_code: str,
    run_id: str,
    raw_text: str,
) -> None:
    if raw_dir is None:
        return

    raw_dir.mkdir(parents=True, exist_ok=True)
    city_slug = city.strip().lower().replace(" ", "-")
    country_slug = country_code.strip().lower()
    filename = f"{city_slug}-{country_slug}_{run_id}_air_pollution.json"

    (raw_dir / filename).write_text(raw_text, encoding="utf-8")