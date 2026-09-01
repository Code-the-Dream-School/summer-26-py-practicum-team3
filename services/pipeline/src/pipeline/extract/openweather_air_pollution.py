"""OpenWeather Air Pollution History API extract module."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pipeline.common.logging import get_logger
from pathlib import Path
from typing import Any

from pydantic import SecretStr
import requests

from pipeline.common.config import settings

log = get_logger(__name__)

OPENWEATHER_AIR_POLLUTION_URL = "https://api.openweathermap.org/data/2.5/air_pollution/history"


class OpenWeatherRequestError(Exception):
    """Raised when OpenWeather request cannot be executed cleanly."""


def _mask_api_key_in_url(url: str, key_val: str) -> str:
    if key_val and key_val in url:
        return url.replace(key_val, "**********")
    return url


def _validate_location(lat: float, lon: float) -> None:
    if not (-90.0 <= lat <= 90.0):
        raise ValueError(f"Latitude must be between -90.0 and 90.0, got {lat}.")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError(f"Longitude must be between -180.0 and 180.0, got {lon}.")


def _validate_window(start: datetime, end: datetime) -> None:
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end timestamps must be timezone-aware (UTC).")
    if end < start:
        raise ValueError(f"start timestamp ({start}) must be before end timestamp ({end}).")


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
    raw_response: dict[str, Any] | None
    raw_file_path: Path | None
    error_message: str | None = None
    city_id: str | None = None
    state_code: str | None = None
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def to_transform_input(record: RawAirPollutionRecord) -> dict[str, Any]:
    """Converts a RawAirPollutionRecord into the dictionary envelope expected by the transform stage."""
    return {
        "status": record.status,
        "payload": record.raw_response,
        "city_id": record.city_id,
        "city_name": record.city,
        "country_code": record.country_code,
        "state_code": record.state_code,
        "lat": record.lat,
        "lon": record.lon,
        "retrieved_at": record.retrieved_at,
        "run_id": record.run_id,
        "pipeline_run_id": record.pipeline_run_id,
    }


def _save_raw_response(
    raw_dir: Path | None,
    city: str,
    country_code: str,
    run_id: str,
    payload: Any,
) -> Path | None:
    if raw_dir is None:
        return None
    raw_dir.mkdir(parents=True, exist_ok=True)
    city_slug = city.strip().lower().replace(" ", "_")
    country_slug = country_code.strip().lower()
    file_path = raw_dir / f"{city_slug}-{country_slug}_{run_id}_air_pollution.json"
    with open(file_path, "w", encoding="utf-8") as f:
        if isinstance(payload, str):
            f.write(payload)
        else:
            json.dump(payload, f, indent=2, default=str)
    return file_path


def _request_history(
    lat: float,
    lon: float,
    start: datetime,
    end: datetime,
    raw_dir: Path | None = None,
    city: str = "",
    country_code: str = "",
    run_id: str = "",
    api_key: str | SecretStr | None = None,
    http_client: Any = None,
) -> tuple[dict[str, Any] | None, Path | None]:
    resolved_key: str | None = None
    if api_key is None:
        if settings.openweather_api_key:
            resolved_key = (
                settings.openweather_api_key.get_secret_value()
                if isinstance(settings.openweather_api_key, SecretStr)
                else str(settings.openweather_api_key)
            )
    elif isinstance(api_key, SecretStr):
        resolved_key = api_key.get_secret_value()
    else:
        resolved_key = str(api_key)

    params = {
        "lat": lat,
        "lon": lon,
        "start": int(start.timestamp()),
        "end": int(end.timestamp()),
        "appid": resolved_key or "",
    }

    client = http_client or requests

    try:
        response = client.get(OPENWEATHER_AIR_POLLUTION_URL, params=params, timeout=10)
    except Exception as exc:
        msg = str(exc)
        if resolved_key:
            msg = _mask_api_key_in_url(msg, resolved_key)
        raise OpenWeatherRequestError(f"Network request failed: {msg}") from exc

    status_code = getattr(response, "status_code", None)

    # 1. Save the raw response to disk first (raw before parse)
    raw_text = getattr(response, "text", "")
    raw_file_path = _save_raw_response(
        raw_dir=raw_dir,
        city=city,
        country_code=country_code,
        run_id=run_id,
        payload=raw_text,
    )

    if status_code != 200:
        try:
            data = response.json()
        except Exception:
            data = None
        err_msg = f"OpenWeather returned status {status_code}"
        if isinstance(data, dict) and "message" in data:
            err_msg += f": {data['message']}"
        raise OpenWeatherRequestError(err_msg)

    # 2. Parse JSON (status is 200 here, body is expected to be valid JSON)
    try:
        data = response.json()
    except Exception as exc:
        raise OpenWeatherRequestError(f"Invalid JSON response from OpenWeather: {exc}") from exc

    # 3. If the response is valid JSON, rewrite it with pretty formatting (if needed)
    if isinstance(data, (dict, list)):
        _save_raw_response(
            raw_dir=raw_dir,
            city=city,
            country_code=country_code,
            run_id=run_id,
            payload=data,
        )

    
    if not isinstance(data, dict):
        raise OpenWeatherRequestError(f"Expected JSON object from OpenWeather, got {type(data).__name__}")

    return data, raw_file_path


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
    city_id: str | None = None,
    state_code: str | None = None,
    api_key: str | SecretStr | None = None,
    http_client: Any = None,
) -> RawAirPollutionRecord:
    _validate_location(lat=lat, lon=lon)
    _validate_window(start=start, end=end)

    resolved_city_id = city_id or f"{country_code.lower()}-{city.lower().replace(' ', '-')}"
    retrieved_at = datetime.now(timezone.utc)
    raw_file_path: Path | None = None

    try:
        data, raw_file_path = _request_history(
            lat=lat,
            lon=lon,
            start=start,
            end=end,
            raw_dir=raw_dir,
            city=city,
            country_code=country_code,
            run_id=run_id,
            api_key=api_key,
            http_client=http_client,
        )
        retrieved_at = datetime.now(timezone.utc)

        records_list = data.get("list") if data else None
        status = "empty" if not records_list else "ok"

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
            raw_response=data,
            raw_file_path=raw_file_path,
            error_message=None,
            city_id=resolved_city_id,
            state_code=state_code,
            retrieved_at=retrieved_at,
        )

    except OpenWeatherRequestError as exc:
        retrieved_at = datetime.now(timezone.utc)
        log.warning(
            "Failed to fetch air pollution history from OpenWeather",
            extra={"city": city, "country": country_code, "error": str(exc), "run_id": run_id, "pipeline_run_id": pipeline_run_id},
        )

        # 4. Compute the file path in case it was written before the error
        city_slug = city.strip().lower().replace(" ", "_")
        country_slug = country_code.strip().lower()
        candidate_file = (
            raw_dir / f"{city_slug}-{country_slug}_{run_id}_air_pollution.json"
            if raw_dir is not None
            else None
        )
        persisted_path = candidate_file if candidate_file and candidate_file.exists() else None

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
            raw_file_path=persisted_path,
            error_message=str(exc),
            city_id=resolved_city_id,
            state_code=state_code,
            retrieved_at=retrieved_at,
        )