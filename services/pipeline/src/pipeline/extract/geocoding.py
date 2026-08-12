from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import requests

from pipeline.config import settings

logger = logging.getLogger(__name__)

GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"


@dataclass(frozen=True)
class Coordinates:
    lat: float
    lon: float
    source: str


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
                return Coordinates(
                    lat=results[0]["lat"],
                    lon=results[0]["lon"],
                    source="geocoded",
                )

            logger.warning(
                "Geocoding API returned no results for %s, %s.",
                city,
                country_code,
            )

    except (requests.RequestException, ValueError, KeyError) as exc:
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