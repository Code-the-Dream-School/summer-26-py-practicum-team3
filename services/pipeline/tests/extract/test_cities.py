from __future__ import annotations

import json

import pytest

from pipeline.common.logging import ContextFormatter
from pipeline.extract.cities import log as cities_log
from pipeline.extract.cities import read_cities


def write_cities_file(tmp_path, cities):
    path = tmp_path / "cities.json"
    path.write_text(json.dumps(cities))
    return path


def valid_city(**overrides):
    city = {
        "city_name": "Las Vegas",
        "country_code": "US",
        "city_id": "las-vegas",
        "timezone": "America/Los_Angeles",
        "active": True,
    }
    city.update(overrides)
    return city


def test_read_cities_returns_valid_city(tmp_path):
    path = write_cities_file(tmp_path, [valid_city()])

    cities = read_cities(path)

    assert len(cities) == 1
    assert cities[0].city_name == "Las Vegas"
    assert cities[0].city == "Las Vegas"
    assert cities[0].country_code == "US"
    assert cities[0].city_id == "las-vegas"
    assert cities[0].timezone == "America/Los_Angeles"
    assert cities[0].active is True


def test_read_cities_returns_state_alias(tmp_path):
    path = write_cities_file(
        tmp_path,
        [valid_city(state_code="NV")],
    )

    cities = read_cities(path)

    assert cities[0].state_code == "NV"
    assert cities[0].state == "NV"


@pytest.mark.parametrize(
    "field",
    ["city_name", "country_code", "city_id", "timezone", "active"],
)
def test_read_cities_skips_missing_required_field(tmp_path, field):
    city = valid_city()
    del city[field]

    path = write_cities_file(tmp_path, [city])

    cities = read_cities(path)

    assert cities == []


@pytest.mark.parametrize(
    "field",
    ["city_name", "country_code", "city_id", "timezone"],
)
def test_read_cities_skips_whitespace_required_field(tmp_path, field):
    city = valid_city(**{field: "   "})

    path = write_cities_file(tmp_path, [city])

    cities = read_cities(path)

    assert cities == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("city_name", 123),
        ("city_id", 123),
    ],
)
def test_read_cities_skips_non_string_required_fields(
    tmp_path,
    field,
    value,
):
    path = write_cities_file(
        tmp_path,
        [valid_city(**{field: value})],
    )

    cities = read_cities(path)

    assert cities == []


def test_read_cities_skips_invalid_country_code(tmp_path):
    path = write_cities_file(
        tmp_path,
        [valid_city(country_code="XX")],
    )

    cities = read_cities(path)

    assert cities == []


def test_read_cities_skips_invalid_timezone(tmp_path):
    path = write_cities_file(
        tmp_path,
        [valid_city(timezone="Invalid/Timezone")],
    )

    cities = read_cities(path)

    assert cities == []


@pytest.mark.parametrize("value", ["true", "false", 1, 0, None])
def test_read_cities_skips_invalid_active_value(tmp_path, value):
    path = write_cities_file(
        tmp_path,
        [valid_city(active=value)],
    )

    cities = read_cities(path)

    assert cities == []


def test_read_cities_skips_invalid_entry_but_keeps_valid_entry(tmp_path):
    path = write_cities_file(
        tmp_path,
        [
            valid_city(city_id="invalid", country_code="XX"),
            valid_city(city_id="las-vegas"),
        ],
    )

    cities = read_cities(path)

    assert len(cities) == 1
    assert cities[0].city_id == "las-vegas"


def test_read_cities_raises_for_duplicate_city_ids(tmp_path):
    path = write_cities_file(
        tmp_path,
        [
            valid_city(city_id="las-vegas"),
            valid_city(city_id="las-vegas", city_name="Another City"),
        ],
    )

    with pytest.raises(ValueError, match="Duplicate city_id"):
        read_cities(path)


def test_read_cities_returns_empty_for_missing_path(tmp_path):
    path = tmp_path / "missing.json"

    cities = read_cities(path)

    assert cities == []


def test_read_cities_returns_empty_for_none_path():
    cities = read_cities(None)

    assert cities == []


def test_read_cities_returns_empty_for_empty_file(tmp_path):
    path = write_cities_file(tmp_path, [])

    cities = read_cities(path)

    assert cities == []


def test_read_cities_raises_for_non_list_json(tmp_path):
    path = tmp_path / "cities.json"
    path.write_text(json.dumps({"city_name": "Las Vegas"}))

    with pytest.raises(ValueError, match="JSON list"):
        read_cities(path)


def test_cities_logger_uses_shared_context_formatter():
    """
    Verifies that the module-level logger goes through the shared get_logger()
    helper and is configured with ContextFormatter, instead of falling back
    to a raw stdlib logging.getLogger() with no formatter attached.
    """
    handlers = cities_log.handlers
    assert len(handlers) > 0, "Logger should have at least one handler attached"
    
    # Verify that at least one handler uses the required formatter
    has_context_formatter = any(
        isinstance(h.formatter, ContextFormatter) for h in handlers
    )
    assert has_context_formatter, "Logger must use ContextFormatter to preserve extraction context"