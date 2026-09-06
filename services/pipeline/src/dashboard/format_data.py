"""Shared formatting helpers and constants for the Streamlit dashboard pages.

Every page (Summary / City detail / Compare) imports its AQI presentation and
time formatting from here, so the three views stay consistent and none of them
has to keep its own copy of the mapping.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

# OpenWeather AQI scale (1-5) -> (label, status icon).
# Kept as a (label, icon) pair because pages unpack it directly:
#     label_text, icon = AQI_COLORS.get(aqi, UNKNOWN_AQI)
AQI_COLORS: dict[int, tuple[str, str]] = {
    1: ("Good", "🟢"),
    2: ("Fair", "🟡"),
    3: ("Moderate", "🟠"),
    4: ("Poor", "🔴"),
    5: ("Very Poor", "🟣"),
}

# The same scale as hex colors, for charts or custom HTML/CSS styling.
AQI_HEX: dict[int, str] = {
    1: "#2e7d32",  # Good
    2: "#558b2f",  # Fair
    3: "#f57c00",  # Moderate
    4: "#d32f2f",  # Poor
    5: "#7b1fa2",  # Very Poor
}

UNKNOWN_AQI: tuple[str, str] = ("Unknown", "⚪")
UNKNOWN_HEX: str = "#666666"

# Readings older than this are flagged as stale. Deliberately a timedelta so
# pages can compare it directly against (now - observed_at).
STALE_THRESHOLD: timedelta = timedelta(hours=3)

# Values that show up in place of a real missing marker in string columns.
_MISSING_TEXT = {"", "null", "none", "nan", "n/a"}


def ensure_utc(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime, assuming naive input is already UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def format_relative_time(observed_at: datetime | None) -> str:
    """Format an observation timestamp as a readable relative string.

    Args:
        observed_at: UTC datetime of the observation, or None.

    Returns:
        A string such as "Just now", "15 mins ago", "2 hours ago", "3 days ago".
    """
    if observed_at is None:
        return "Unknown"

    seconds = int((datetime.now(timezone.utc) - ensure_utc(observed_at)).total_seconds())
    if seconds < 60:
        return "Just now"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min{'s' if minutes > 1 else ''} ago"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours > 1 else ''} ago"

    days = hours // 24
    return f"{days} day{'s' if days > 1 else ''} ago"


def is_stale(observed_at: datetime | None, now: datetime | None = None) -> bool:
    """Return True when a reading is older than STALE_THRESHOLD.

    A missing timestamp counts as stale: we cannot claim the data is current.
    """
    if observed_at is None:
        return True
    reference = ensure_utc(now) if now is not None else datetime.now(timezone.utc)
    return (reference - ensure_utc(observed_at)) > STALE_THRESHOLD


def aqi_display(aqi: int | None, aqi_label: str | None = None) -> tuple[str, str]:
    """Resolve the text and icon to show for an AQI value.

    The text prefers `aqi_label` as computed by the pipeline and stored on
    air_pollution_gold, falling back to the local mapping so the UI never shows
    a bare number. The icon always comes from the local mapping.
    """
    label, icon = AQI_COLORS.get(aqi, UNKNOWN_AQI) if aqi is not None else UNKNOWN_AQI
    from_db = (aqi_label or "").strip()
    return (from_db or label), icon


def aqi_hex(aqi: int | None) -> str:
    """Return the hex color for an AQI value, or a neutral grey when unknown."""
    if aqi is None:
        return UNKNOWN_HEX
    return AQI_HEX.get(aqi, UNKNOWN_HEX)


def _clean(value: Any) -> str:
    """Normalize an optional text field, treating placeholder values as missing."""
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in _MISSING_TEXT else text


def city_label(row: Any) -> str:
    """Build the display label for a city row: "Seattle (US, WA)".

    Accepts anything with dict-style access (a psycopg dict_row or a pandas
    Series), so every page labels a city the same way.
    """
    city = _clean(row["city_name"])
    country = _clean(row["country_code"])
    state = _clean(row.get("state_code"))

    location = country
    if state:
        location = f"{country}, {state}" if country else state
    return f"{city} ({location})" if location else city
