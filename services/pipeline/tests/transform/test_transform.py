from datetime import datetime, timezone

from pipeline.transform.transform import transform_raw_response


def make_raw_response(observations):
    return {
        "city_id": "us-san-francisco-ca",
        "city_name": "San Francisco",
        "country_code": "US",
        "state_code": "CA",
        "lat": 37.7749,
        "lon": -122.4194,
        "api": "OpenWeather Air Pollution API",
        "endpoint": "/data/2.5/air_pollution/history",
        "start": "2024-07-03T00:00:00Z",
        "end": "2024-07-03T23:59:59Z",
        "retrieved_at": "2024-07-04T00:00:00Z",
        "run_id": "run-2024-07-03-001",
        "pipeline_run_id": "pipeline-2024-07-03-001",
        "status": 200,
        "payload": {
            "coord": {
                "lon": -122.4194,
                "lat": 37.7749,
            },
            "list": observations,
        },
    }


def make_observation(
    dt=1720009600,
    aqi=2,
    pm2_5=4.3,
):
    return {
        "dt": dt,
        "main": {
            "aqi": aqi,
        },
        "components": {
            "co": 201.94,
            "no": 0.0,
            "no2": 1.2,
            "o3": 68.6,
            "so2": 0.6,
            "pm2_5": pm2_5,
            "pm10": 5.1,
            "nh3": 0.12,
        },
    }


def test_transform_one_observation():
    raw_response = make_raw_response([
        make_observation()
    ])

    result = transform_raw_response(raw_response)

    assert len(result) == 1

    record = result[0]

    assert record["city_id"] == "us-san-francisco-ca"
    assert record["city_name"] == "San Francisco"
    assert record["country_code"] == "US"
    assert record["state_code"] == "CA"

    assert record["lat"] == 37.7749
    assert record["lon"] == -122.4194

    assert record["observed_at"] == datetime.fromtimestamp(
        1720009600,
        tz=timezone.utc,
    )

    assert record["aqi"] == 2
    assert record["aqi_label"] == "Fair"

    assert record["co"] == 201.94
    assert record["no"] == 0.0
    assert record["no2"] == 1.2
    assert record["o3"] == 68.6
    assert record["so2"] == 0.6
    assert record["pm2_5"] == 4.3
    assert record["pm10"] == 5.1
    assert record["nh3"] == 0.12

    assert record["run_id"] == "run-2024-07-03-001"
    assert record["pipeline_run_id"] == "pipeline-2024-07-03-001"


def test_transform_multiple_observations():
    raw_response = make_raw_response([
        make_observation(
            dt=1720009600,
            aqi=2,
            pm2_5=4.3,
        ),
        make_observation(
            dt=1720013200,
            aqi=1,
            pm2_5=3.8,
        ),
    ])

    result = transform_raw_response(raw_response)

    assert len(result) == 2

    assert result[0]["aqi"] == 2
    assert result[0]["aqi_label"] == "Fair"
    assert result[0]["pm2_5"] == 4.3

    assert result[1]["aqi"] == 1
    assert result[1]["aqi_label"] == "Good"
    assert result[1]["pm2_5"] == 3.8

    assert result[0]["observed_at"] != result[1]["observed_at"]


def test_transform_flattens_nested_api_data():
    raw_response = make_raw_response([
        make_observation()
    ])

    result = transform_raw_response(raw_response)

    record = result[0]

    assert "main" not in record
    assert "components" not in record

    assert record["aqi"] == 2
    assert record["co"] == 201.94
    assert record["pm2_5"] == 4.3


def test_transform_empty_observation_list_returns_empty_list():
    raw_response = make_raw_response([])

    result = transform_raw_response(raw_response)

    assert result == []


def test_transform_missing_optional_pollutant_returns_none():
    observation = make_observation()
    del observation["components"]["pm2_5"]

    raw_response = make_raw_response([observation])

    result = transform_raw_response(raw_response)

    assert len(result) == 1
    assert result[0]["pm2_5"] is None


def test_transform_negative_pollutant_returns_none():
    observation = make_observation()
    observation["components"]["pm2_5"] = -5.0

    raw_response = make_raw_response([observation])

    result = transform_raw_response(raw_response)

    assert len(result) == 1
    assert result[0]["pm2_5"] is None


def test_transform_missing_dt_drops_observation():
    observation = make_observation()
    del observation["dt"]

    raw_response = make_raw_response([observation])

    result = transform_raw_response(raw_response)

    assert result == []


def test_transform_missing_state_code_is_allowed():
    raw_response = make_raw_response([
        make_observation()
    ])
    del raw_response["state_code"]

    result = transform_raw_response(raw_response)

    assert len(result) == 1
    assert result[0]["state_code"] is None