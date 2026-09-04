"""Unit tests for dashboard database query layer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from dashboard.queries import (
    get_cities_comparison,
    get_city_history,
    get_latest_readings,
    list_cities,
)


def _create_mock_connection(return_value: list[dict[str, Any]]) -> MagicMock:
    """Helper to mock a psycopg connection with context-managed cursor."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = return_value

    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = None
    return mock_conn


def test_list_cities() -> None:
    """Verify list_cities executes query with state_code and returns active city records."""
    expected = [
        {"city_id": "berlin-de", "city_name": "Berlin", "country_code": "DE", "state_code": None},
        {"city_id": "london-gb", "city_name": "London", "country_code": "GB", "state_code": None},
    ]
    mock_conn = _create_mock_connection(expected)

    result = list_cities(mock_conn)

    assert result == expected
    cursor = mock_conn.cursor.return_value.__enter__.return_value
    assert cursor.execute.called
    query = cursor.execute.call_args[0][0]
    assert "state_code" in query
    assert "active = true" in query


def test_get_latest_readings() -> None:
    """Verify get_latest_readings returns ranked latest row per city with state_code."""
    now = datetime.now(timezone.utc)
    expected = [
        {
            "city_id": "berlin-de",
            "city_name": "Berlin",
            "country_code": "DE",
            "state_code": None,
            "observed_at": now,
            "aqi": 2,
        },
    ]
    mock_conn = _create_mock_connection(expected)

    result = get_latest_readings(mock_conn)

    assert result == expected
    cursor = mock_conn.cursor.return_value.__enter__.return_value
    assert cursor.execute.called
    query = cursor.execute.call_args[0][0]
    assert "state_code" in query
    assert "active = true" in query


def test_get_city_history() -> None:
    """Verify get_city_history passes string city_id and date boundaries correctly."""
    start = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 2, 0, 0, tzinfo=timezone.utc)
    expected = [
        {
            "city_id": "berlin-de",
            "city_name": "Berlin",
            "country_code": "DE",
            "state_code": None,
            "observed_at": start,
            "aqi": 1,
        },
    ]
    mock_conn = _create_mock_connection(expected)

    result = get_city_history(mock_conn, city_id="berlin-de", start=start, end=end)

    assert result == expected
    cursor = mock_conn.cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 1
    query, params = cursor.execute.call_args[0]
    assert "state_code" in query
    assert "active = true" in query
    assert params == {"city_id": "berlin-de", "start": start, "end": end}


def test_get_city_history_raises_on_naive_datetime() -> None:
    """Verify get_city_history raises ValueError when naive datetimes are provided."""
    naive_dt = datetime(2026, 9, 1, 0, 0)
    aware_dt = datetime(2026, 9, 2, 0, 0, tzinfo=timezone.utc)
    mock_conn = MagicMock()

    with pytest.raises(ValueError, match="timezone-aware"):
        get_city_history(mock_conn, city_id="berlin-de", start=naive_dt, end=aware_dt)

    with pytest.raises(ValueError, match="timezone-aware"):
        get_city_history(mock_conn, city_id="berlin-de", start=aware_dt, end=naive_dt)


def test_get_cities_comparison_with_ids() -> None:
    """Verify get_cities_comparison passes string city_ids list to query."""
    start = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 2, 0, 0, tzinfo=timezone.utc)
    expected = [
        {
            "city_id": "berlin-de",
            "city_name": "Berlin",
            "country_code": "DE",
            "state_code": None,
            "observed_at": start,
            "aqi": 1,
        },
        {
            "city_id": "london-gb",
            "city_name": "London",
            "country_code": "GB",
            "state_code": None,
            "observed_at": start,
            "aqi": 3,
        },
    ]
    mock_conn = _create_mock_connection(expected)

    result = get_cities_comparison(
        mock_conn,
        city_ids=["berlin-de", "london-gb"],
        start=start,
        end=end,
    )

    assert result == expected
    cursor = mock_conn.cursor.return_value.__enter__.return_value
    query, params = cursor.execute.call_args[0]
    assert "state_code" in query
    assert "active = true" in query
    assert params == {"city_ids": ["berlin-de", "london-gb"], "start": start, "end": end}


def test_get_cities_comparison_raises_on_naive_datetime() -> None:
    """Verify get_cities_comparison raises ValueError when naive datetimes are provided."""
    naive_dt = datetime(2026, 9, 1, 0, 0)
    aware_dt = datetime(2026, 9, 2, 0, 0, tzinfo=timezone.utc)
    mock_conn = MagicMock()

    with pytest.raises(ValueError, match="timezone-aware"):
        get_cities_comparison(mock_conn, city_ids=["berlin-de"], start=naive_dt, end=aware_dt)

    with pytest.raises(ValueError, match="timezone-aware"):
        get_cities_comparison(mock_conn, city_ids=["berlin-de"], start=aware_dt, end=naive_dt)


def test_get_cities_comparison_empty_list_returns_immediately() -> None:
    """Verify empty city_ids skips database call and returns empty list."""
    mock_conn = MagicMock()
    start = datetime.now(timezone.utc)
    end = datetime.now(timezone.utc)

    result = get_cities_comparison(mock_conn, city_ids=[], start=start, end=end)

    assert result == []
    mock_conn.cursor.assert_not_called()