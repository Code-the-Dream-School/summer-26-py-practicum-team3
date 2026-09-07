"""Tests for the City Detail dashboard view."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from streamlit.testing.v1 import AppTest

CITY_DETAIL_PAGE = "../../src/dashboard/pages/2_City_Detail.py"

# Patch at the *source* modules (dashboard.db / dashboard.queries), not at
# dashboard.pages.2_City_Detail: AppTest.from_file() execs the page script fresh
# on each run rather than importing it through the normal sys.modules graph, so
# patching the page's own dotted path silently does nothing.
DB_TARGET = "dashboard.db.init_connection"
CITIES_TARGET = "dashboard.queries.list_cities"
HISTORY_TARGET = "dashboard.queries.get_city_history"

CITY = {"city_id": "seattle-us-wa", "city_name": "Seattle", "country_code": "US", "state_code": "WA"}


def _reading(**overrides) -> dict:
    """One get_city_history() row, fresh by default."""
    row = {
        "city_id": "seattle-us-wa",
        "city_name": "Seattle",
        "country_code": "US",
        "state_code": "WA",
        "observed_at": datetime.now(timezone.utc) - timedelta(minutes=5),
        "aqi": 2,
        "co": 201.0,
        "no": 0.1,
        "no2": 1.2,
        "o3": 68.0,
        "so2": 0.5,
        "pm2_5": 4.4,
        "pm10": 5.1,
        "nh3": 0.3,
    }
    row.update(overrides)
    return row


def _mock_connection(coordinates: tuple[float, float] | None) -> MagicMock:
    """A connection whose .cursor() serves _get_latest_coordinates()'s raw query.

    Needed because that helper talks to the connection directly (bypassing
    dashboard.queries), so patching get_city_history alone isn't enough here.
    """
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = (
        {"lat": coordinates[0], "lon": coordinates[1]} if coordinates else None
    )
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.cursor.return_value.__exit__.return_value = None
    return conn


def _run(
    cities: list[dict],
    history: list[dict],
    coordinates: tuple[float, float] | None = (47.6, -122.3),
) -> AppTest:
    with patch(DB_TARGET, return_value=_mock_connection(coordinates)), \
         patch(CITIES_TARGET, return_value=cities), \
         patch(HISTORY_TARGET, return_value=history):
        at = AppTest.from_file(CITY_DETAIL_PAGE)
        at.run()
    return at


def test_no_cities_configured_renders_empty_state() -> None:
    at = _run([], [])

    assert not at.exception
    assert "No cities configured yet." in at.info[0].value


def test_no_history_in_window_renders_empty_state() -> None:
    at = _run([CITY], [])

    assert not at.exception
    assert "No historical readings in this window yet." in at.info[0].value


def test_renders_latest_reading_and_trend_chart() -> None:
    at = _run([CITY], [_reading()])

    assert not at.exception
    assert "Seattle (US, WA)" in [block.value for block in at.subheader]
    assert "Fair" in at.metric[0].value
    assert not at.warning


def test_stale_reading_is_flagged() -> None:
    stale_at = datetime.now(timezone.utc) - timedelta(hours=5)
    at = _run([CITY], [_reading(observed_at=stale_at)])

    assert not at.exception
    assert "Stale data" in at.warning[0].value


def test_metric_and_lookback_selectors_offer_expected_options() -> None:
    at = _run([CITY], [_reading()])

    assert not at.exception
    selectbox_by_label = {box.label: box for box in at.selectbox}
    assert selectbox_by_label["Metric"].options[0] == "AQI"
    assert selectbox_by_label["Lookback window"].options == [
        "1 day",
        "3 days",
        "7 days",
        "14 days",
        "30 days",
    ]


def test_missing_database_url_renders_error_state() -> None:
    with patch(DB_TARGET, side_effect=ValueError("DATABASE_URL must be configured")):
        at = AppTest.from_file(CITY_DETAIL_PAGE)
        at.run()

    assert not at.exception
    assert "Configuration Error" in at.error[0].value


def test_renders_map_when_coordinates_are_known() -> None:
    """AppTest has no dedicated inspector for st.map; no exception is the signal."""
    at = _run([CITY], [_reading()], coordinates=(47.6, -122.3))

    assert not at.exception


def test_skips_map_when_coordinates_are_unknown() -> None:
    at = _run([CITY], [_reading()], coordinates=None)

    assert not at.exception


def test_page_does_not_render_the_landing_banner() -> None:
    """The page must not pull in app.py's top-level UI (duplicate welcome banner)."""
    at = _run([CITY], [_reading()])

    rendered = " ".join(block.value for block in at.markdown) + " ".join(
        block.value for block in at.title
    )
    assert "Welcome to the Air Quality Dashboard" not in rendered
