"""Tests for the Summary dashboard view."""

from unittest.mock import patch
from streamlit.testing.v1 import AppTest

def test_summary_page_renders_without_crashing():
    """Verify that the Summary page executes successfully."""
    # We mock the init_connection so it doesn't try to hit a real DB
    # Patch at the *source* modules (dashboard.app / dashboard.queries), not at
    # dashboard.pages.1_Summary: AppTest.from_file() execs the page script fresh
    # on each run rather than importing it through the normal sys.modules graph,
    # so patching the page's own dotted path silently does nothing (the page's
    # `from dashboard.app import init_connection` / `from dashboard.queries import
    # get_latest_readings` statements re-resolve against the real, unpatched
    # source modules every time). Patching the source modules works because those
    # import statements look up the current attribute on the (shared, cached)
    # source module at each exec.
    with patch("dashboard.app.init_connection", return_value=None), \
         patch("dashboard.queries.get_latest_readings", return_value=[]):
        at = AppTest.from_file("../../src/dashboard/pages/1_Summary.py")
        at.run()

        assert not at.exception
        # Should show the empty state message since we returned []
        assert "No air pollution data available." in at.info[0].value