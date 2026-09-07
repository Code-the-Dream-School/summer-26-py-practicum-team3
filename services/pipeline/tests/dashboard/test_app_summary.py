"""Tests for the Summary dashboard view."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

SUMMARY_PAGE = "../../src/dashboard/pages/1_Summary.py"

# Patch at the *source* modules (dashboard.db / dashboard.queries), not at
# dashboard.pages.1_Summary: AppTest.from_file() execs the page script fresh on
# each run rather than importing it through the normal sys.modules graph, so
# patching the page's own dotted path silently does nothing (its `from ...
# import ...` statements re-resolve against the real source modules every time).
# Patching the source modules works because those imports look up the current
# attribute on the (shared, cached) source module at each exec.
DB_TARGET = "dashboard.db.init_connection"
QUERY_TARGET = "dashboard.queries.get_latest_readings"


def _reading(**overrides) -> dict:
    """One get_latest_readings() row, fresh by default."""
    row = {
        "city_id": "seattle-us-wa",
        "city_name": "Seattle",
        "country_code": "US",
        "state_code": "WA",
        "observed_at": datetime.now(timezone.utc) - timedelta(minutes=5),
        "aqi": 2,
        "aqi_label": "Fair",
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


def _run(readings: list[dict]) -> AppTest:
    with patch(DB_TARGET, return_value=None), patch(QUERY_TARGET, return_value=readings):
        at = AppTest.from_file(SUMMARY_PAGE)
        at.run()
    return at


def test_empty_state_when_no_readings() -> None:
    """No rows yet renders an explicit empty state, not a blank page."""
    at = _run([])

    assert not at.exception
    assert "No air pollution data available." in at.info[0].value


def test_renders_city_card_with_label_from_database() -> None:
    """A reading renders without error and shows the pipeline's aqi_label."""
    at = _run([_reading()])

    assert not at.exception
    assert "Seattle (US, WA)" in [block.value for block in at.subheader]
    assert "Fair" in at.metric[0].value
    # Fresh data must not raise the stale badge.
    assert not at.warning


def test_stale_reading_is_flagged() -> None:
    """A reading older than the stale threshold gets a warning badge."""
    stale_at = datetime.now(timezone.utc) - timedelta(hours=5)
    at = _run([_reading(observed_at=stale_at)])

    assert not at.exception
    assert "Stale data" in at.warning[0].value


def test_sort_selectbox_offers_the_three_orders() -> None:
    """The sort dropdown is present once there is data to sort."""
    at = _run([_reading(), _reading(city_id="berlin-de", city_name="Berlin", state_code=None)])

    assert not at.exception
    assert at.selectbox[0].options == ["City name", "AQI (worst first)", "Last updated"]


def test_missing_database_url_renders_error_state() -> None:
    """A configuration error surfaces as a message, not a traceback."""
    with patch(DB_TARGET, side_effect=ValueError("DATABASE_URL must be configured")):
        at = AppTest.from_file(SUMMARY_PAGE)
        at.run()

    assert not at.exception
    assert "Configuration Error" in at.error[0].value


def test_page_does_not_render_the_landing_banner() -> None:
    """The page must not pull in app.py's top-level UI (duplicate welcome banner)."""
    at = _run([_reading()])

    rendered = " ".join(block.value for block in at.markdown) + " ".join(
        block.value for block in at.title
    )
    assert "Welcome to the Air Quality Dashboard" not in rendered
