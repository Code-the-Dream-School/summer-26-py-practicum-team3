from unittest.mock import patch, Mock
from datetime import datetime, timezone

import requests

from pipeline.extract.openweather_air_pollution import fetch_air_pollution_history
from pipeline.extract.geocoding import geocode_city

# Test 1: Successful location → data flow

@patch("pipeline.extract.geocoding.requests.get")
def test_geocode_city_success(mock_get):
  # Arrange
  mock_response = Mock()
  mock_response.status_code = 200
  mock_response.text = '[{"lat": 40.7128, "lon": -74.0060}]'
  mock_response.json.return_value = [
    {
      "lat": 40.7128,
      "lon": -74.0060,
    }
  ]
  
  mock_get.return_value = mock_response
  
  # Act
  result = geocode_city("New York", "US")

  # Assert
  assert result is not None
  assert result.lat == 40.7128
  assert result.lon == -74.0060
  assert result.source == "geocoded"


# Test 2: Invalid location
@patch("pipeline.extract.geocoding.requests.get")
def test_geocode_city_returns_none_for_unknown_city(mock_get):
  # Arrange
  mock_response = Mock()
  mock_response.status_code = 200
  mock_response.text = "[]"
  mock_response.json.return_value = []

  mock_get.return_value = mock_response

  # Act
  result = geocode_city("Definitely Not A Real City", "US")

  # Assert
  assert result is None


# Test 3: API failure uses fallback
@patch("pipeline.extract.geocoding.requests.get")
def test_geocode_city_uses_fallback_when_api_fails(mock_get):
  # Arrange
  mock_get.side_effect = requests.RequestException("API unavailable")

  # Act
  result = geocode_city("New York", "US")

  # Assert
  assert result is not None
  assert result.source == "fallback"
  assert result.lat == 40.7128
  assert result.lon == -74.0060


# Test 4: Successful air-pollution extraction
def test_fetch_air_pollution_history_success():
  # Arrange
  mock_response = Mock()
  mock_response.status_code = 200
  mock_response.text = '{"list": [{"main": {"aqi": 2}}]}'
  mock_response.json.return_value = {
    "list": [
      {"dt": 1606482000,
       "main": {"aqi" : 2},
       "components": {"pm2_5" : 13.448}}]}

  http_client = Mock()
  http_client.get.return_value = mock_response
  
  start = datetime(2020, 11, 27, tzinfo=timezone.utc)
  end = datetime(2020, 11, 28, tzinfo=timezone.utc)

  # Act
  result = fetch_air_pollution_history(
    raw_dir=None,
    city="New York",
    country_code="US",
    lat=40.7128,
    lon=-74.0060,
    start=start,
    end=end,
    run_id="test-run",
    pipeline_run_id=1,
    api_key="test-key",
    http_client=http_client
  )
  
  # Assert
  assert result.status == "ok"
  assert result.raw_response is not None
  assert result.raw_response["list"][0]["main"]["aqi"] == 2

# Test 5: Malformed API response
def test_fetch_air_pollution_history_malformed_response():
  # Arrange
  mock_response = Mock()
  mock_response.status_code = 200
  mock_response.text = "not json"
  mock_response.json.side_effect = ValueError("Invalid JSON")
  
  http_client = Mock()
  http_client.get.return_value = mock_response
  
  start = datetime(2020, 11, 27, tzinfo=timezone.utc)
  end = datetime(2020, 11, 28, tzinfo=timezone.utc)
  
  # Act
  result = fetch_air_pollution_history(
    raw_dir=None,
      city="New York",
      country_code="US",
      lat=40.7128,
      lon=-74.0060,
      start=start,
      end=end,
      run_id="test-run",
      pipeline_run_id=1,
      api_key="test-key",
      http_client=http_client
    )
  
  # Assert
  assert result.status == "error"
  assert result.raw_response is None
  assert result.error_message is not None
  
# Verification notes:
#
# Automated tests:
# - Successful geocoding: passed
# - Invalid location: passed
# - Geocoding API failure with fallback: passed
# - Successful air-pollution extraction: passed
# - Malformed air-pollution response: passed
#
# Missing API key:
# The current configuration allows an empty API key value, and the
# extraction clients do not explicitly reject it. Therefore, a distinct
# missing-API-key failure test cannot currently be added without defining
# the expected behavior first.