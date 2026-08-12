from unittest.mock import patch


# Test 1: Successful location → data flow

# Unsure if we are geocoding or hardcoding?
@patch("teams_module.geocoding_function")
@patch("teams_module.pollution_function")
def test_successful_location_to_data(
    mock_pollution,
    mock_geocoding,
):
    # Arrange
    city = "New York City"

    # currently returning long/lat
    mock_geocoding.return_value = [-74.0060, 40.7128]

    mock_pollution.return_value = {
  "coord": {
    "lon": -74.0060,
    "lat": 40.7128
  },
  "list": [
    {
      "main": {
        "aqi": 2
      },
      "components": {
        "co": 204.0,
        "no": 1.2,
        "no2": 35.0,
        "o3": 38.0,
        "so2": 2.0,
        "pm2_5": 16.0,
        "pm10": 32.0,
        "nh3": 0.5
      },
      "dt": 1786482600
    }
  ]
}

    # Act
    # TODO update air_quality_function to be the correct function name
    # result = air_quality_function(city)

    # Assert
    # TODO determine expected_result from functions return value
    # assert result == expected_result

    # Not sure if we are doing geocoding or hard coding so might remove
    mock_geocoding.assert_called_once_with(city)
    # confirm what is passed once we know what will be extracted
    # mock_pollution.assert_called_once_with(-74.0060, 40.7128)


# Test 2: Invalid location
# TODO: Confirm whether invalid city input is handled by the extraction layer or by city configuration validation.
@patch("teams_module.geocoding_function")
def test_invalid_location(mock_geocoding):
    # Arrange
    city = "Invalid City"

    # Make geocoding behave like an invalid/unrecognized city.
    # TODO replace with actual response for the invalid City
    mock_geocoding.return_value = ...

    # Act
	  # TODO update air_quality_function to be the correct function name
    # result = air_quality_function(city)

    # Assert
    # TODO update expected_results with what the return value is for invalid city
    # assert result == expected_results


# Test 3: Empty API response

@patch("teams_module.api_function")
def test_empty_response(mock_api):
    # Arrange
    mock_api.return_value = {}

    # Act
    # TODO update function name to actual function name
    # result = air_quality_function("New York City")

    # Assert
    # TODO update expected_results with what is returned for empty or malformed API response
    # assert result == expected_results


# Test 4: Missing API key / configuration

def test_missing_api_key(monkeypatch):
    # Arrange
    # TODO confirm this is the name of the API key in 
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)

    # Act
    # TODO call the correct function here
    # result = air_pollution_function(city)

    # Assert
    # TODO confirm how missing API key is handled in the actual functions