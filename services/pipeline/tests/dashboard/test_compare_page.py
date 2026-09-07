"""Tests for the Compare dashboard view."""

from datetime import datetime, timezone
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

PAGE_PATH = "../../src/dashboard/pages/3_Compare.py"

FAKE_CITIES = [
    {"city_id": "berlin-de", "city_name": "Berlin", "country_code": "DE", "state_code": None},
    {"city_id": "austin-us", "city_name": "Austin", "country_code": "US", "state_code": "TX"},
]


def test_compare_page_empty_city_list():
    """No active cities configured -> empty-state message, no crash."""
    # Patch the source modules (dashboard.db / dashboard.queries),
    # not the page's own dotted path - AppTest.from_file() execs the page fresh each run,
    # so only source-module patches take effect.
    with patch("dashboard.db.init_connection", return_value=None), \
         patch("dashboard.queries.list_cities", return_value=[]):
        at = AppTest.from_file(PAGE_PATH)
        at.run()

        assert not at.exception
        assert "No cities configured yet." in at.info[0].value


def test_compare_page_empty_history_window():
    """Cities exist, but the historical query returns nothing in range."""
    with patch("dashboard.db.init_connection", return_value=None), \
         patch("dashboard.queries.list_cities", return_value=FAKE_CITIES), \
         patch("dashboard.queries.get_cities_comparison", return_value=[]):
        at = AppTest.from_file(PAGE_PATH)
        at.run()

        assert not at.exception
        assert "No historical readings in this window yet." in at.info[0].value


def test_compare_page_renders_with_data():
    """Happy path: history has rows, table and chart render without error."""
    now = datetime.now(timezone.utc)
    fake_history = [
        {
            "city_id": "berlin-de", "city_name": "Berlin", "country_code": "DE",
            "state_code": None, "observed_at": now, "aqi": 1, "aqi_label": "Good",
            "co": 200.0, "no": 0.5, "no2": 10.0, "o3": 60.0, "so2": 5.0,
            "pm2_5": 8.0, "pm10": 15.0, "nh3": 1.0,
        },
        {
            "city_id": "austin-us", "city_name": "Austin", "country_code": "US",
            "state_code": "TX", "observed_at": now, "aqi": 3, "aqi_label": "Moderate",
            "co": 400.0, "no": 1.0, "no2": 20.0, "o3": 80.0, "so2": 10.0,
            "pm2_5": 20.0, "pm10": 35.0, "nh3": 2.0,
        },
    ]
    with patch("dashboard.db.init_connection", return_value=None), \
         patch("dashboard.queries.list_cities", return_value=FAKE_CITIES), \
         patch("dashboard.queries.get_cities_comparison", return_value=fake_history):
        at = AppTest.from_file(PAGE_PATH)
        at.run()

        assert not at.exception
        # Freshly-timestamped rows -> no stale/missing warnings should fire.
        assert len(at.warning) == 0