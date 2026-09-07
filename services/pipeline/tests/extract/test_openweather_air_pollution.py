"""Unit tests for the OpenWeather air pollution extract client."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests
from pipeline.extract.openweather_air_pollution import (
    _validate_location,
    _validate_window,
    fetch_air_pollution_history,
)


@pytest.fixture
def valid_window():
    """Helper fixture to create a valid 24-hour UTC window."""
    start = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc)
    return start, end


@pytest.fixture
def mock_ok_response():
    """Helper fixture to simulate a standard 200 OK response with 1 record."""
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.text = '{"list": [{"dt": 1600000000, "main": {"aqi": 1}}]}'
    mock_resp.json.return_value = {
        "list": [{"dt": 1600000000, "main": {"aqi": 1}}]
    }
    return mock_resp


# ============================================================================
# 1. Validation Tests
# ============================================================================

def test_validate_location_valid():
    """Valid coordinates should not raise any errors."""
    _validate_location(47.86, -121.81)


def test_validate_location_latitude_too_high():
    """Latitude above 90 degrees must raise ValueError."""
    with pytest.raises(ValueError, match="between"):
        _validate_location(90.1, 0.0)


def test_validate_location_latitude_too_low():
    """Latitude below -90 degrees must raise ValueError."""
    with pytest.raises(ValueError, match="between"):
        _validate_location(-90.1, 0.0)


def test_validate_location_longitude_too_high():
    """Longitude above 180 degrees must raise ValueError."""
    with pytest.raises(ValueError, match="between"):
        _validate_location(0.0, 180.1)


def test_validate_location_longitude_too_low():
    """Longitude below -180 degrees must raise ValueError."""
    with pytest.raises(ValueError, match="between"):
        _validate_location(0.0, -180.1)


def test_validate_window_valid(valid_window):
    """Valid time range with timezone info should pass validation."""
    start, end = valid_window
    _validate_window(start, end)


def test_validate_window_naive_datetime():
    """Datetimes without timezone info must be rejected."""
    start = datetime(2026, 8, 1)  # noqa: DTZ001 - Intentionally naive for testing
    end = datetime(2026, 8, 2, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="timezone-aware"):
        _validate_window(start, end)


def test_validate_window_invalid_range():
    """Start date after end date must be rejected."""
    start = datetime(2026, 8, 2, tzinfo=timezone.utc)
    end = datetime(2026, 8, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="must be before end"):
        _validate_window(start, end)


def test_fetch_validation_error_propagates_unhandled(valid_window):
    """Validation errors should raise directly instead of returning error records."""
    start, end = valid_window
    with pytest.raises(ValueError, match="between"):
        fetch_air_pollution_history(
            raw_dir=None,
            city="Sultan",
            country_code="US",
            lat=999.0,  # Invalid latitude
            lon=-121.81,
            start=start,
            end=end,
            run_id="run1",
            pipeline_run_id=1,
            api_key="test_key",
        )


# ============================================================================
# 2. Successful Extraction ("ok")
# ============================================================================

def test_fetch_success_ok(valid_window, mock_ok_response):
    """Successful API call with data should return status 'ok'."""
    start, end = valid_window
    mock_client = Mock()
    mock_client.get.return_value = mock_ok_response

    record = fetch_air_pollution_history(
        raw_dir=None,
        city="Sultan",
        country_code="US",
        lat=47.86,
        lon=-121.81,
        start=start,
        end=end,
        run_id="run1",
        pipeline_run_id=1,
        api_key="test_key",
        http_client=mock_client,
    )

    assert record.status == "ok"
    assert record.error_message is None
    assert record.raw_response == {"list": [{"dt": 1600000000, "main": {"aqi": 1}}]}


# ============================================================================
# 3. Empty Result ("empty")
# ============================================================================

def test_fetch_success_empty(valid_window):
    """Successful 200 OK response with no data records should return status 'empty'."""
    start, end = valid_window
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.text = '{"list": []}'
    mock_resp.json.return_value = {"list": []}

    mock_client = Mock()
    mock_client.get.return_value = mock_resp

    record = fetch_air_pollution_history(
        raw_dir=None,
        city="Sultan",
        country_code="US",
        lat=47.86,
        lon=-121.81,
        start=start,
        end=end,
        run_id="run1",
        pipeline_run_id=1,
        api_key="test_key",
        http_client=mock_client,
    )

    assert record.status == "empty"
    assert record.raw_response == {"list": []}
    assert record.error_message is None


# ============================================================================
# 4. Network Failures & API Key Masking
# ============================================================================

def test_fetch_network_failure_masks_api_key(valid_window):
    """Network connection exceptions should be caught and hide the API key."""
    start, end = valid_window
    secret_key = "secret_api_key_123"

    mock_client = Mock()
    mock_client.get.side_effect = requests.RequestException(
        f"Connection failed for url?appid={secret_key}"
    )

    record = fetch_air_pollution_history(
        raw_dir=None,
        city="Sultan",
        country_code="US",
        lat=47.86,
        lon=-121.81,
        start=start,
        end=end,
        run_id="run1",
        pipeline_run_id=1,
        api_key=secret_key,
        http_client=mock_client,
    )

    assert record.status == "error"
    assert record.raw_response is None
    assert secret_key not in record.error_message
    assert "***" in record.error_message


# ============================================================================
# 5. HTTP Error Code (500) & API Key Masking
# ============================================================================

def test_fetch_status_500_masks_api_key(valid_window):
    """HTTP 500 server errors should return status 'error' and mask sensitive keys."""
    start, end = valid_window
    secret_key = "secret_api_key_123"

    mock_resp = Mock()
    mock_resp.status_code = 500
    mock_resp.text = f"Server Error details with appid={secret_key}"

    mock_client = Mock()
    mock_client.get.return_value = mock_resp

    record = fetch_air_pollution_history(
        raw_dir=None,
        city="Sultan",
        country_code="US",
        lat=47.86,
        lon=-121.81,
        start=start,
        end=end,
        run_id="run1",
        pipeline_run_id=1,
        api_key=secret_key,
        http_client=mock_client,
    )

    assert record.status == "error"
    assert secret_key not in record.error_message
    assert "OpenWeather returned status 500" in record.error_message


# ============================================================================
# 6. Invalid JSON Response Body
# ============================================================================

def test_fetch_invalid_json_payload(valid_window):
    """Non-JSON response bodies (e.g. HTML error pages) should result in error status."""
    start, end = valid_window

    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>Gateway Timeout</html>"
    mock_resp.json.side_effect = ValueError("Invalid JSON format")

    mock_client = Mock()
    mock_client.get.return_value = mock_resp

    record = fetch_air_pollution_history(
        raw_dir=None,
        city="Sultan",
        country_code="US",
        lat=47.86,
        lon=-121.81,
        start=start,
        end=end,
        run_id="run1",
        pipeline_run_id=1,
        api_key="test_key",
        http_client=mock_client,
    )

    assert record.status == "error"
    assert "Invalid JSON response" in record.error_message


# ============================================================================
# 7. Non-Dictionary Payload (Array instead of Object)
# ============================================================================

def test_fetch_non_dict_json_payload(valid_window):
    """Responses containing a JSON list instead of a JSON object should return error status."""
    start, end = valid_window

    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.text = "[1, 2, 3]"
    mock_resp.json.return_value = [1, 2, 3]

    mock_client = Mock()
    mock_client.get.return_value = mock_resp

    record = fetch_air_pollution_history(
        raw_dir=None,
        city="Sultan",
        country_code="US",
        lat=47.86,
        lon=-121.81,
        start=start,
        end=end,
        run_id="run1",
        pipeline_run_id=1,
        api_key="test_key",
        http_client=mock_client,
    )

    assert record.status == "error"
    assert "Expected JSON object from OpenWeather, got list" in record.error_message


# ============================================================================
# 8. Raw File Persistence (Even for Errors)
# ============================================================================

def test_raw_file_persisted_even_on_error(tmp_path: Path, valid_window):
    """Raw response text must be saved to disk even if the API returns an error."""
    start, end = valid_window
    raw_html_error = "<html>500 Internal Error</html>"

    mock_resp = Mock()
    mock_resp.status_code = 500
    mock_resp.text = raw_html_error

    mock_client = Mock()
    mock_client.get.return_value = mock_resp

    fetch_air_pollution_history(
        raw_dir=tmp_path,
        city="Sultan",
        country_code="US",
        lat=47.86,
        lon=-121.81,
        start=start,
        end=end,
        run_id="run123",
        pipeline_run_id=1,
        api_key="test_key",
        http_client=mock_client,
    )

    expected_file = tmp_path / "sultan-us_run123_air_pollution.json"
    assert expected_file.exists()
    assert expected_file.read_text(encoding="utf-8") == raw_html_error


# ============================================================================
# 9. Optional raw_dir (None)
# ============================================================================

def test_fetch_with_raw_dir_none(valid_window, mock_ok_response):
    """When raw_dir is None, no file operations should occur and extraction succeeds."""
    start, end = valid_window
    mock_client = Mock()
    mock_client.get.return_value = mock_ok_response

    record = fetch_air_pollution_history(
        raw_dir=None,
        city="Sultan",
        country_code="US",
        lat=47.86,
        lon=-121.81,
        start=start,
        end=end,
        run_id="run1",
        pipeline_run_id=1,
        api_key="test_key",
        http_client=mock_client,
    )

    assert record.status == "ok"


# ============================================================================
# 10. Missing API Key Resolution from Settings
# ============================================================================

def test_fetch_missing_api_key_returns_error_status(valid_window, monkeypatch):
    """If API key is missing or unconfigured in settings, return 401 error status."""
    start, end = valid_window

    from pipeline.common.config import settings
    monkeypatch.setattr(settings, "openweather_api_key", "")

    mock_resp = Mock()
    mock_resp.status_code = 401
    mock_resp.text = '{"cod": 401, "message": "Invalid API key."}'

    mock_client = Mock()
    mock_client.get.return_value = mock_resp

    record = fetch_air_pollution_history(
        raw_dir=None,
        city="Sultan",
        country_code="US",
        lat=47.86,
        lon=-121.81,
        start=start,
        end=end,
        run_id="run1",
        pipeline_run_id=1,
        api_key=None,  # Fallback to settings
        http_client=mock_client,
    )

    assert record.status == "error"
    assert "OpenWeather returned status 401" in record.error_message