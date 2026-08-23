# Raw API Response Contract

## Purpose

This document defines what context should travel with each raw API response from the extract layer.

The pipeline uses two OpenWeather APIs:

* **Geocoding API** — converts a city name into latitude and longitude.
* **Air Pollution API** — uses latitude and longitude to get air pollution data.

The goal is to keep enough information with each raw response for later processing and storage.

This document does not define the final database or storage schema.

## 1. Geocoding API

The Geocoding API is used to convert the city information from the location input into coordinates.

The request can include:

* City name
* State, when available
* Country code

The response provides:

* Latitude
* Longitude
* City and country information returned by the API

The coordinates returned by the Geocoding API are then used to request air pollution data.

### Geocoding Response Context

Each geocoding response should include:

| Context         | Fields                                               | Description                                        |
| --------------- | ---------------------------------------------------- | -------------------------------------------------- |
| Source location | `city_id`, `city_name`, `country_code`, `state_code` | Identifies the requested city.                     |
| Coordinates     | `lat`, `lon`                                         | Coordinates returned by the API or fallback table. |
| API             | `api`                                                | OpenWeather Geocoding API.                         |
| Endpoint        | `endpoint`                                           | Geocoding endpoint used.                           |
| Retrieval time  | `retrieved_at`                                       | UTC time when the response was received.           |
| Pipeline run    | `run_id`, `pipeline_run_id`                          | Connects the response to a pipeline run.           |
| Status          | `status`                                             | Whether the request succeeded or failed.           |
| Source          | `coordinate_source`                                  | `geocoded`,`fallback` or absent when no coordinates are found.                          |
| Raw payload     | `payload`                                            | Original API response, when available.             |

The Geocoding API does not have a request time window.

If the Geocoding API fails, the extract layer uses the hardcoded coordinate table as a fallback.

If the city is not found in the API or the fallback table, the city is treated as missing required coordinates. No air pollution request is made for that city, and the failure is logged.

## 2. Air Pollution API

The Air Pollution API uses the latitude and longitude from the geocoding step to retrieve air pollution data.

For historical data, the request includes:

* `lat`
* `lon`
* `start`
* `end`
* `appid`

### Air Pollution Response Context

Each air pollution response should include:

| Context         | Fields                                                             | Description                               |
| --------------- | ------------------------------------------------------------------ | ----------------------------------------- |
| Source location | `city_id`, `city_name`, `country_code`, `state_code`, `lat`, `lon` | Identifies the city and coordinates used. |
| API             | `api`                                                              | OpenWeather Air Pollution API.            |
| Endpoint        | `endpoint`                                                         | Historical air pollution endpoint.        |
| Request window  | `start`, `end`                                                     | UTC time range requested.                 |
| Retrieval time  | `retrieved_at`                                                     | UTC time when the response was received.  |
| Pipeline run    | `run_id`, `pipeline_run_id`                                        | Connects the response to a pipeline run.  |
| Status          | `status`                                                           | Whether the request succeeded or failed.  |
| Raw payload     | `payload`                                                          | Original OpenWeather response.            |

The raw payload should be kept unchanged by the extract layer.

## 3. Important Air Pollution Fields

The following fields appear important for future dashboard work:

* `dt` — observation time
* `main.aqi` — Air Quality Index
* `components.co` — Carbon monoxide
* `components.no` — Nitrogen monoxide
* `components.no2` — Nitrogen dioxide
* `components.o3` — Ozone
* `components.so2` — Sulphur dioxide
* `components.pm2_5` — PM2.5
* `components.pm10` — PM10
* `components.nh3` — Ammonia

The `coord` field can also be used to verify that the response matches the requested coordinates.

These fields are identified for future dashboard work only. They do not define the final storage schema.

## 4. Storage Layer Handoff

The future storage layer should be able to accept the raw response together with its context.

For both APIs, it should be able to handle:

* Source location
* API and endpoint
* Raw payload
* Retrieval time
* Pipeline run information
* Response status

For air pollution requests, it also needs:

* Request start time
* Request end time

For geocoding requests, it also needs:

* Coordinate source (`geocoded` or `fallback`)
* Coordinates used or returned

The current extract layer stores raw responses under `data/raw`. The final storage location and database design have not been decided.

## 5. Design Decisions

### 1. Shared response envelope

Geocoding and air pollution responses use the same basic response envelope.

Fields that do not apply to a specific API are optional. For example, geocoding responses do not have `start` and `end` values.

### 2. Location identification

`city_id` is the main location identifier.

`city_name`, `country_code`, and `state_code` are also included when available. This makes raw responses easier to understand without requiring a lookup against the city configuration.

### 3. Failed API responses

If an API returns a response, the raw response is saved even when the status is non-200.

If a network error occurs and no response is received, there is no raw payload to save. The failure should instead be logged.

If geocoding fails and the fallback table also has no coordinates, no air pollution request is made for that city. The missing coordinates are logged as a missing required value.

### 4. Repeated requests

Repeated requests are kept rather than overwritten.

`run_id` and `pipeline_run_id` identify which pipeline run produced each response.

### 5. Raw storage

The current extract layer saves raw responses as JSON files under `data/raw`.

The future storage layer may load these responses into PostgreSQL. This contract does not depend on the final database design.

### 6. Retention

The storage layer will determine how long raw responses are retained.

The Sprint 3 contract only defines the context needed to store and manage the responses later.

### 7. Raw payload

The original API payload is preserved inside `payload` without changing its structure.

The response context is stored alongside the payload so the raw response can be understood and processed later.

## 6. Sprint 3 Handoff

The extract layer should return raw API responses with enough context to identify:

* Where the data came from
* Which API and endpoint were used
* What time window was requested, when applicable
* When the response was retrieved
* Which pipeline run produced it
* The original API payload
* Whether coordinates came from the Geocoding API or the fallback table

If coordinates cannot be found from either the Geocoding API or the fallback table, no air pollution response is created for that city. The missing coordinate condition is logged.

The storage layer can use this contract as its input without requiring the extract layer to define the final database schema.

## 7. Response Envelope

The shared response structure is:

```text
RawResponse
├── city_id
├── city_name
├── country_code
├── state_code
├── lat                 # optional
├── lon                 # optional
├── api
├── endpoint
├── coordinate_source    # optional
├── start                # optional
├── end                  # optional
├── retrieved_at
├── run_id
├── pipeline_run_id
├── status
└── payload
```

`start` and `end` are used for air pollution requests and are not required for geocoding responses.

`coordinate_source` identifies whether coordinates came from the Geocoding API or the hardcoded fallback.

For an unsuccessful geocoding attempt with no fallback coordinates, `lat` and `lon` are not available and no air pollution request is created.
