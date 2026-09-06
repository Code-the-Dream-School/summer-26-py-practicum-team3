"""Tests for the dashboard's shared formatting helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from dashboard.format_data import (
    AQI_COLORS,
    STALE_THRESHOLD,
    aqi_display,
    aqi_hex,
    city_label,
    ensure_utc,
    format_relative_time,
    is_stale,
)


def _ago(**kwargs) -> datetime:
    return datetime.now(timezone.utc) - timedelta(**kwargs)


@pytest.mark.parametrize(
    "observed_at,expected",
    [
        (None, "Unknown"),
        (_ago(seconds=10), "Just now"),
        (_ago(minutes=1), "1 min ago"),
        (_ago(minutes=15), "15 mins ago"),
        (_ago(hours=1), "1 hour ago"),
        (_ago(hours=5), "5 hours ago"),
        (_ago(days=3), "3 days ago"),
    ],
)
def test_format_relative_time(observed_at: datetime | None, expected: str) -> None:
    assert format_relative_time(observed_at) == expected


def test_format_relative_time_treats_naive_datetime_as_utc() -> None:
    """observed_at comes back naive from some drivers; it must not raise."""
    naive = (datetime.now(timezone.utc) - timedelta(minutes=30)).replace(tzinfo=None)
    assert format_relative_time(naive) == "30 mins ago"


def test_ensure_utc_converts_other_offsets() -> None:
    other = datetime(2026, 9, 6, 12, 0, tzinfo=timezone(timedelta(hours=-7)))
    assert ensure_utc(other) == datetime(2026, 9, 6, 19, 0, tzinfo=timezone.utc)


def test_is_stale_uses_the_shared_threshold() -> None:
    now = datetime.now(timezone.utc)
    assert not is_stale(now - STALE_THRESHOLD + timedelta(minutes=1), now)
    assert is_stale(now - STALE_THRESHOLD - timedelta(minutes=1), now)


def test_missing_timestamp_counts_as_stale() -> None:
    """Without a timestamp we cannot claim the reading is current."""
    assert is_stale(None)


def test_aqi_colors_unpack_as_label_and_icon() -> None:
    """Pages unpack this mapping directly, so the pair shape is part of the contract."""
    label, icon = AQI_COLORS[3]
    assert label == "Moderate"
    assert icon


def test_aqi_display_prefers_the_database_label() -> None:
    text, icon = aqi_display(3, "Moderate air quality")
    assert text == "Moderate air quality"
    assert icon == AQI_COLORS[3][1]


def test_aqi_display_falls_back_to_the_local_mapping() -> None:
    assert aqi_display(1, None) == AQI_COLORS[1]
    assert aqi_display(1, "  ") == AQI_COLORS[1]


def test_aqi_display_handles_unknown_values() -> None:
    text, _ = aqi_display(None)
    assert text == "Unknown"
    text, _ = aqi_display(99)
    assert text == "Unknown"


def test_aqi_hex_falls_back_to_neutral_grey() -> None:
    assert aqi_hex(1).startswith("#")
    assert aqi_hex(None) == aqi_hex(99)


@pytest.mark.parametrize(
    "row,expected",
    [
        ({"city_name": "Seattle", "country_code": "US", "state_code": "WA"}, "Seattle (US, WA)"),
        ({"city_name": "Berlin", "country_code": "DE", "state_code": None}, "Berlin (DE)"),
        ({"city_name": "Berlin", "country_code": "DE", "state_code": "null"}, "Berlin (DE)"),
        ({"city_name": "Berlin", "country_code": "DE", "state_code": "  "}, "Berlin (DE)"),
    ],
)
def test_city_label(row: dict, expected: str) -> None:
    assert city_label(row) == expected
