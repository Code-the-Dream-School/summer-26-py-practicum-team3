from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import requests
from pydantic import BaseModel, ValidationError

from pipeline.common.config import settings

logger = logging.getLogger(__name__)

GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"


class Coordinates(BaseModel):
    """Geographic coordinates and their source."""

    lat: float
    lon: float
    source: Literal["geocoded", "fallback"]


class GeocodingResult(BaseModel):
    """Validated coordinates returned by the geocoding API."""

    lat: float
    lon: float


FALLBACK_COORDINATES: dict[
    tuple[str, str | None, str],
    tuple[float, float],
] = {
    ("LAS-VEGAS", None, "US"): (36.1699, -115.1398),
    ("NEW-YORK", None, "US"): (40.7128, -74.0060),
    ("LOS-ANGELES", None, "US"): (34.0522, -118.2437),
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
    try:
        response = requests.get(
            GEOCODING_URL,
            params={
                "q": _build_query(city, country_code, state),
                "limit": 1,
                "appid": settings.openweather_api_key,
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

        if response.status_code != 200:
            logger.warning(
                "Geocoding API request failed for %s, %s: HTTP %s",
                city,
                country_code,
                response.status_code,
            )
        else:
            results = response.json()

            if results:
                result = GeocodingResult.model_validate(results[0])

                return Coordinates(
                    lat=result.lat,
                    lon=result.lon,
                    source="geocoded",
                )

            logger.warning(
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
        logger.warning(
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
        logger.warning(
            "Using fallback coordinates for %s, %s.",
            city,
            country_code,
        )

        return Coordinates(
            lat=fallback[0],
            lon=fallback[1],
            source="fallback",
        )

    logger.warning(
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
    country_key = country_code.strip().upper()

    return FALLBACK_COORDINATES.get(
        (city_key, state_key, country_key)
    )


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

    (raw_dir / filename).write_text(response)


def _city_filename(
    city: str,
    country_code: str,
    state: str | None,
) -> str:
    parts = [city]

    if state:
        parts.append(state)

    parts.append(country_code)

    return "-".join(
        part.strip().lower().replace(" ", "-")
        for part in parts
    )


def _normalize_city(city: str) -> str:
    return city.strip().upper().replace(" ", "-")


def _normalize_state(state: str | None) -> str | None:
    if state is None:
        return None

    return state.strip().upper().replace(" ", "-")