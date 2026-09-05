from __future__ import annotations

import pytest
from pydantic import SecretStr

from pipeline.common.logging import ContextFormatter
from pipeline.extract import geocoding


class MockResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        return self._json_data


def test_geocode_city_returns_api_coordinates(monkeypatch, tmp_path):
    response = MockResponse(
        status_code=200,
        json_data=[
            {
                "lat": 36.1699,
                "lon": -115.1398,
            }
        ],
        text='[{"lat": 36.1699, "lon": -115.1398}]',
    )

    def mock_get(*args, **kwargs):
        return response

    monkeypatch.setattr(geocoding.requests, "get", mock_get)

    coordinates = geocoding.geocode_city(
        city="Las Vegas",
        country_code="US",
        raw_dir=tmp_path,
    )

    assert coordinates is not None
    assert coordinates.lat == 36.1699
    assert coordinates.lon == -115.1398
    assert coordinates.source == "geocoded"


def test_geocode_city_uses_fallback_when_api_fails(
    monkeypatch,
    tmp_path,
):
    response = MockResponse(
        status_code=500,
        text="Internal Server Error",
    )

    def mock_get(*args, **kwargs):
        return response

    monkeypatch.setattr(geocoding.requests, "get", mock_get)

    coordinates = geocoding.geocode_city(
        city="Las Vegas",
        country_code="US",
        raw_dir=tmp_path,
    )

    assert coordinates is not None
    assert coordinates.lat == 36.1699
    assert coordinates.lon == -115.1398
    assert coordinates.source == "fallback"


def test_geocode_city_uses_fallback_when_api_returns_no_results(
    monkeypatch,
    tmp_path,
):
    response = MockResponse(
        status_code=200,
        json_data=[],
        text="[]",
    )

    def mock_get(*args, **kwargs):
        return response

    monkeypatch.setattr(geocoding.requests, "get", mock_get)

    coordinates = geocoding.geocode_city(
        city="Las Vegas",
        country_code="US",
        raw_dir=tmp_path,
    )

    assert coordinates is not None
    assert coordinates.source == "fallback"


def test_geocode_city_uses_fallback_on_request_error(
    monkeypatch,
    tmp_path,
):
    def mock_get(*args, **kwargs):
        raise geocoding.requests.RequestException("Network error")

    monkeypatch.setattr(geocoding.requests, "get", mock_get)

    coordinates = geocoding.geocode_city(
        city="Las Vegas",
        country_code="US",
        raw_dir=tmp_path,
    )

    assert coordinates is not None
    assert coordinates.source == "fallback"


def test_geocode_city_returns_none_when_api_and_fallback_fail(
    monkeypatch,
    tmp_path,
):
    response = MockResponse(
        status_code=500,
        text="Internal Server Error",
    )

    def mock_get(*args, **kwargs):
        return response

    monkeypatch.setattr(geocoding.requests, "get", mock_get)

    coordinates = geocoding.geocode_city(
        city="Unknown City",
        country_code="US",
        raw_dir=tmp_path,
    )

    assert coordinates is None


def test_geocode_city_saves_raw_response(tmp_path, monkeypatch):
    response_text = '[{"lat": 36.1699, "lon": -115.1398}]'

    response = MockResponse(
        status_code=200,
        json_data=[
            {
                "lat": 36.1699,
                "lon": -115.1398,
            }
        ],
        text=response_text,
    )

    def mock_get(*args, **kwargs):
        return response

    monkeypatch.setattr(geocoding.requests, "get", mock_get)

    geocoding.geocode_city(
        city="Las Vegas",
        country_code="US",
        state="NV",
        raw_dir=tmp_path,
    )

    output = tmp_path / "las-vegas-nv-us_geocoding.json"

    assert output.exists()
    assert output.read_text() == response_text


def test_geocode_city_filenames_include_state(
    monkeypatch,
    tmp_path,
):
    response = MockResponse(
        status_code=200,
        json_data=[],
        text="[]",
    )

    monkeypatch.setattr(
        geocoding.requests,
        "get",
        lambda *args, **kwargs: response,
    )

    geocoding.geocode_city(
        city="Portland",
        country_code="US",
        state="OR",
        raw_dir=tmp_path,
    )

    geocoding.geocode_city(
        city="Portland",
        country_code="US",
        state="ME",
        raw_dir=tmp_path,
    )

    assert (tmp_path / "portland-or-us_geocoding.json").exists()
    assert (tmp_path / "portland-me-us_geocoding.json").exists()


def test_geocode_city_uses_fallback_for_normalized_city_name(
    monkeypatch,
    tmp_path,
):
    response = MockResponse(
        status_code=500,
        text="Internal Server Error",
    )

    monkeypatch.setattr(
        geocoding.requests,
        "get",
        lambda *args, **kwargs: response,
    )

    coordinates = geocoding.geocode_city(
        city="  Las   Vegas  ",
        country_code=" us ",
        raw_dir=tmp_path,
    )

    assert coordinates is not None
    assert coordinates.lat == 36.1699
    assert coordinates.lon == -115.1398
    assert coordinates.source == "fallback"


def test_geocode_city_uses_fallback_when_api_response_is_missing_lat(
    monkeypatch,
    tmp_path,
):
    response = MockResponse(
        status_code=200,
        json_data=[
            {
                "lon": -115.1398,
            }
        ],
        text='[{"lon": -115.1398}]',
    )

    monkeypatch.setattr(
        geocoding.requests,
        "get",
        lambda *args, **kwargs: response,
    )

    coordinates = geocoding.geocode_city(
        city="Las Vegas",
        country_code="US",
        raw_dir=tmp_path,
    )

    assert coordinates is not None
    assert coordinates.source == "fallback"


def test_geocode_city_uses_fallback_when_api_response_is_missing_lon(
    monkeypatch,
    tmp_path,
):
    response = MockResponse(
        status_code=200,
        json_data=[
            {
                "lat": 36.1699,
            }
        ],
        text='[{"lat": 36.1699}]',
    )

    monkeypatch.setattr(
        geocoding.requests,
        "get",
        lambda *args, **kwargs: response,
    )

    coordinates = geocoding.geocode_city(
        city="Las Vegas",
        country_code="US",
        raw_dir=tmp_path,
    )

    assert coordinates is not None
    assert coordinates.source == "fallback"


def test_geocode_city_uses_fallback_when_api_returns_unexpected_response(
    monkeypatch,
    tmp_path,
):
    response = MockResponse(
        status_code=200,
        json_data={
            "error": "Unexpected response",
        },
        text='{"error": "Unexpected response"}',
    )

    monkeypatch.setattr(
        geocoding.requests,
        "get",
        lambda *args, **kwargs: response,
    )

    coordinates = geocoding.geocode_city(
        city="Las Vegas",
        country_code="US",
        raw_dir=tmp_path,
    )

    assert coordinates is not None
    assert coordinates.lat == 36.1699
    assert coordinates.lon == -115.1398
    assert coordinates.source == "fallback"


def test_geocode_city_filenames_distinguish_spaces_and_hyphens(
    monkeypatch,
    tmp_path,
):
    response = MockResponse(
        status_code=200,
        json_data=[],
        text="[]",
    )

    monkeypatch.setattr(
        geocoding.requests,
        "get",
        lambda *args, **kwargs: response,
    )

    geocoding.geocode_city(
        city="Winston Salem",
        country_code="US",
        raw_dir=tmp_path,
    )

    geocoding.geocode_city(
        city="Winston-Salem",
        country_code="US",
        raw_dir=tmp_path,
    )

    assert (tmp_path / "winston-salem-us_geocoding.json").exists()

    assert (tmp_path / "winston--salem-us_geocoding.json").exists()


def test_geocode_city_uses_fallback_when_api_key_is_not_configured(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        geocoding.settings,
        "openweather_api_key",
        SecretStr(""),
    )

    def mock_get(*args, **kwargs):
        pytest.fail("API should not be called when API key is not configured")

    monkeypatch.setattr(
        geocoding.requests,
        "get",
        mock_get,
    )

    coordinates = geocoding.geocode_city(
        city="Las Vegas",
        country_code="US",
        raw_dir=tmp_path,
    )

    assert coordinates is not None
    assert coordinates.lat == 36.1699
    assert coordinates.lon == -115.1398
    assert coordinates.source == "fallback"


def test_geocoding_logger_uses_shared_context_formatter():
    """
    Verifies that the module-level logger goes through the shared get_logger()
    helper and is configured with ContextFormatter.
    """
    handlers = geocoding.log.handlers
    assert len(handlers) > 0, "Logger should have at least one handler attached"
    
    # Verify that at least one handler uses the required formatter
    has_context_formatter = any(
        isinstance(h.formatter, ContextFormatter) for h in handlers
    )
    assert has_context_formatter, "Logger must use ContextFormatter to preserve extraction context"