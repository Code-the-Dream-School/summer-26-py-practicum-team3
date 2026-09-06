from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import requests
from pydantic import BaseModel, ValidationError

from pipeline.common.config import settings
from pipeline.common.logging import get_logger

log = get_logger(__name__)

GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"


class Coordinates(BaseModel):
    """Geographic coordinates and their source."""

    lat: float
    lon: float
    source: Literal["geocoded", "fallback"]
    http_status: int | None = None
    payload: Any | None = None


class GeocodingResult(BaseModel):
    """Validated coordinates returned by the geocoding API."""

    lat: float
    lon: float


def _normalize_name(value: str) -> str:
    """Normalize a name for consistent fallback lookups."""
    return re.sub(r"\s+", " ", value.strip().upper())


def _normalize_city(city: str) -> str:
    return _normalize_name(city)


def _normalize_state(state: str | None) -> str | None:
    if state is None:
        return None

    return _normalize_name(state)


def _normalize_country(country_code: str) -> str:
    return country_code.strip().upper()


_RAW_FALLBACK_COORDINATES = [
    ("Las Vegas", None, "US", 36.1699, -115.1398),
    ("New York", None, "US", 40.7128, -74.0060),
    ("Los Angeles", None, "US", 34.0522, -118.2437),
]


# Matched by city name alone if an exact (city, state, country) match isn't found — see
# _get_fallback_coordinates. This does not disambiguate same-named cities in different states
# (e.g. a real "Las Vegas, NM" would still resolve to these Nevada coordinates); acceptable here
# since this table exists purely as a dev/demo safety net, not a production geocoding source.
FALLBACK_COORDINATES: dict[
    tuple[str, str | None, str],
    tuple[float, float],
] = {
    (
        _normalize_city(city),
        _normalize_state(state),
        _normalize_country(country_code),
    ): (lat, lon)
    for city, state, country_code, lat, lon in _RAW_FALLBACK_COORDINATES
}


def geocode_city(
    city: str,
    country_code: str,
    state: str | None = None,
    raw_dir: Path | None = None,
) -> Coordinates | None:
    """Resolve a city's coordinates using the geocoding API and fallbacks.

    Args:
        city: City name to geocode.
        country_code: ISO country code for the city.
        state: Optional state or region used to narrow the geocoding query.
        raw_dir: Optional directory where the raw geocoding API response
            is saved.

    Returns:
        A Coordinates object with the source set to "geocoded" or "fallback",
        or None if coordinates cannot be found from either source.
    """

    api_key = settings.openweather_api_key.get_secret_value().strip()

    if not api_key:
        log.warning(
            "OpenWeather API key is not configured; skipping geocoding API request."
        )

        fallback = _get_fallback_coordinates(
            city=city,
            country_code=country_code,
            state=state,
        )

        if fallback is not None:
            return Coordinates(
                lat=fallback[0],
                lon=fallback[1],
                source="fallback",
            )

        return None

    http_status: int | None = None
    payload: Any | None = None

    try:
        response = requests.get(
            GEOCODING_URL,
            params={
                "q": _build_query(city, country_code, state),
                "limit": 1,
                "appid": api_key,
            },
            timeout=10,
        )

        _save_raw_response(
            raw_dir=raw_dir,
            city=city,
            country_code=country_code,
            state=state,
            response=response.text,
        )

        http_status = response.status_code
        try:
            payload = response.json()
        except Exception:  # noqa: BLE001
            payload = {"raw_text": response.text}

        if response.status_code != 200:
            log.warning(
                "Geocoding API request failed for %s, %s: HTTP %s",
                city,
                country_code,
                response.status_code,
            )
        else:
            results = payload

            if results:
                result = GeocodingResult.model_validate(results[0])

                return Coordinates(
                    lat=result.lat,
                    lon=result.lon,
                    source="geocoded",
                    http_status=http_status,
                    payload=payload,
                )

            log.warning(
                "Geocoding API returned no results for %s, %s.",
                city,
                country_code,
            )

    except (
        requests.RequestException,
        ValueError,
        KeyError,
        ValidationError,
    ) as exc:
        log.warning(
            "Geocoding API request failed for %s, %s: %s",
            city,
            country_code,
            exc,
        )

    fallback = _get_fallback_coordinates(
        city=city,
        country_code=country_code,
        state=state,
    )

    if fallback is not None:
        log.warning(
            "Using fallback coordinates for %s, %s.",
            city,
            country_code,
        )

        return Coordinates(
            lat=fallback[0],
            lon=fallback[1],
            source="fallback",
            http_status=http_status,
            payload=payload,
        )

    log.warning(
        "No coordinates found for %s, %s.",
        city,
        country_code,
    )

    return None


def _build_query(
    city: str,
    country_code: str,
    state: str | None,
) -> str:
    parts = [city]

    if state:
        parts.append(state)

    parts.append(country_code)

    return ",".join(parts)


def _get_fallback_coordinates(
    city: str,
    country_code: str,
    state: str | None,
) -> tuple[float, float] | None:
    city_key = _normalize_city(city)
    state_key = _normalize_state(state)
    country_key = _normalize_country(country_code)

    coordinates = FALLBACK_COORDINATES.get((city_key, state_key, country_key))
    if coordinates is not None:
        return coordinates

    # Retry ignoring state: entries are keyed by state=None, so a config that provides a real
    # state_code (e.g. "NV") wouldn't otherwise match.
    return FALLBACK_COORDINATES.get((city_key, None, country_key))


def _save_raw_response(
    raw_dir: Path | None,
    city: str,
    country_code: str,
    state: str | None,
    response: str,
) -> None:
    if raw_dir is None:
        return

    raw_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{_city_filename(city, country_code, state)}_geocoding.json"

    (raw_dir / filename).write_text(response, encoding="utf-8")


def _city_filename(
    city: str,
    country_code: str,
    state: str | None,
) -> str:
    parts = [_filename_part(city)]

    if state:
        parts.append(_filename_part(state))

    parts.append(_filename_part(country_code))

    return "-".join(parts)


def _filename_part(value: str) -> str:
    """Convert a value to a safe, readable filename component."""
    value = value.strip().lower()
    value = value.replace("-", "--")
    return re.sub(r"\s+", "-", value)
