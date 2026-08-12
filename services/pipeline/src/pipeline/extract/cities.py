from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pycountry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class City:
    city_name: str
    country_code: str
    city_id: str
    timezone: str
    active: bool
    state_code: str | None = None

    @property
    def city(self) -> str:
        return self.city_name

    @property
    def state(self) -> str | None:
        return self.state_code


def read_cities(path: Path | None) -> list[City]:
    if path is None:
        logger.warning("Cities input source is missing.")
        return []

    if not path.exists():
        logger.warning("Cities input file does not exist: %s", path)
        return []

    with path.open() as file:
        raw_cities = json.load(file)

    if not isinstance(raw_cities, list):
        raise ValueError("Cities input must contain a JSON list.")

    if not raw_cities:
        logger.warning("Cities input file is empty: %s", path)
        return []

    cities: list[City] = []

    for index, raw_city in enumerate(raw_cities):
        city = _build_city(raw_city, index)

        if city is not None:
            cities.append(city)

    _validate_unique_city_ids(cities)

    return cities


def _build_city(raw_city: object, index: int) -> City | None:
    if not isinstance(raw_city, dict):
        logger.warning(
            "Skipping city entry #%d because it is not an object.",
            index,
        )
        return None

    required_fields = [
        "city_name",
        "country_code",
        "city_id",
        "timezone",
        "active",
    ]

    missing_fields = [
        field
        for field in required_fields
        if _is_missing(raw_city.get(field))
    ]

    if missing_fields:
        logger.warning(
            "Skipping city entry #%d because required fields are missing: %s",
            index,
            ", ".join(missing_fields),
        )
        return None

    city_name = raw_city["city_name"]
    city_id = raw_city["city_id"]
    country_code = raw_city["country_code"]
    timezone = raw_city["timezone"]
    active = raw_city["active"]

    if not _is_valid_required_string(city_name):
        logger.warning(
            "Skipping city entry #%d because city_name must be a non-empty string.",
            index,
        )
        return None

    if not _is_valid_required_string(city_id):
        logger.warning(
            "Skipping city entry #%d because city_id must be a non-empty string.",
            index,
        )
        return None

    if not _is_valid_country_code(country_code):
        logger.warning(
            "Skipping city entry #%d because country_code is invalid: %r",
            index,
            country_code,
        )
        return None

    if not _is_valid_timezone(timezone):
        logger.warning(
            "Skipping city entry #%d because timezone is invalid: %r",
            index,
            timezone,
        )
        return None

    if not isinstance(active, bool):
        logger.warning(
            "Skipping city entry #%d because active must be true or false.",
            index,
        )
        return None

    return City(
        city_name=city_name.strip(),
        country_code=country_code.strip().upper(),
        city_id=city_id.strip(),
        timezone=timezone.strip(),
        active=active,
        state_code=_clean_optional_string(raw_city.get("state_code")),
    )


def _is_missing(value: object) -> bool:
    return value is None or (
        isinstance(value, str) and not value.strip()
    )


def _is_valid_required_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_valid_country_code(value: object) -> bool:
    if not isinstance(value, str):
        return False

    country_code = value.strip().upper()

    return pycountry.countries.get(alpha_2=country_code) is not None


def _is_valid_timezone(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False

    try:
        ZoneInfo(value.strip())
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def _clean_optional_string(value: object) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()
        return value or None

    return str(value)


def _validate_unique_city_ids(cities: list[City]) -> None:
    city_ids = [city.city_id for city in cities]

    if len(city_ids) != len(set(city_ids)):
        raise ValueError("Duplicate city_id found in cities configuration.")