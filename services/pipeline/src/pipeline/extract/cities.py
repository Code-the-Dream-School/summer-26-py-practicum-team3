from __future__ import annotations

import json
import logging
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pycountry
from pydantic import BaseModel, StrictBool, ValidationError, field_validator

logger = logging.getLogger(__name__)


class City(BaseModel):
    """Validated city configuration record."""

    city_name: str
    country_code: str
    city_id: str
    timezone: str
    active: StrictBool
    state_code: str | None = None

    @field_validator("city_name", "city_id")
    @classmethod
    def validate_required_string(cls, value: str) -> str:
        """Ensure required string fields are not empty."""
        value = value.strip()

        if not value:
            raise ValueError("must be a non-empty string")

        return value

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, value: str) -> str:
        """Ensure the country code is a valid ISO alpha-2 code."""
        value = value.strip().upper()

        if pycountry.countries.get(alpha_2=value) is None:
            raise ValueError(f"invalid country code: {value!r}")

        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        """Ensure the timezone is a valid timezone."""
        value = value.strip()

        if not value:
            raise ValueError("must be a non-empty string")

        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"invalid timezone: {value!r}")

        return value

    @field_validator("state_code", mode="before")
    @classmethod
    def clean_state_code(cls, value: object) -> str | None:
        """Normalize the optional state code."""
        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()
            return value or None

        return str(value)

    @property
    def city(self) -> str:
        return self.city_name

    @property
    def state(self) -> str | None:
        return self.state_code


def read_cities(path: Path | None) -> list[City]:
    """Load and validate cities from a JSON configuration file.

    Args:
        path: Path to the cities JSON file. If None or the file does not
            exist, a warning is logged and an empty list is returned.

    Returns:
        A list of validated City records. Invalid entries are skipped and
        logged, so the returned list may be shorter than the input or empty.

    Raises:
        ValueError: If the JSON content is not a list or if duplicate
            city_id values are found.
    """
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

    try:
        return City(**raw_city)
    except ValidationError as error:
        logger.warning(
            "Skipping city entry #%d because it is invalid: %s",
            index,
            error,
        )
        return None


def _validate_unique_city_ids(cities: list[City]) -> None:
    city_ids = [city.city_id for city in cities]

    if len(city_ids) != len(set(city_ids)):
        raise ValueError("Duplicate city_id found in cities configuration.")