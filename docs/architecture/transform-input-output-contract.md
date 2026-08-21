# Transform Input and Output Contract

## Purpose

The Transform stage converts raw air-pollution API responses produced by the Extract stage into clean application records for downstream use.

This contract defines:

* What the Transform stage receives.
* The extraction context available with each raw response.
* The granularity of each transformed record.
* How raw API fields map to clean fields.
* What the Transform stage returns.
* An example transformed record.

This contract describes **application data**, not a final PostgreSQL schema. The output may later be persisted in PostgreSQL or another storage system, but the Transform contract is independent of that storage design.

See `data_flow_diagram.md` for the overall pipeline flow and where the Transform stage sits between Extract and Load.

---

## 1. Transform Input

The Transform stage receives the `RawResponse` produced by the Extract stage.

Transform operates on the raw air-pollution API response. Geocoding responses provide extraction context and coordinates but are not themselves transformed into air-quality records.

### RawResponse

Each raw air-pollution API response contains the following context:

| Field             | Required | Description                                             |
| ----------------- | -------- | ------------------------------------------------------- |
| `city_id`         | Yes      | Stable identifier for the configured city.              |
| `city_name`       | Yes      | Human-readable city name.                               |
| `country_code`    | Yes      | ISO 3166-1 alpha-2 country code.                        |
| `state_code`      | No       | State/province/region code when available.              |
| `lat`             | Yes      | Latitude used for the air-pollution request.            |
| `lon`             | Yes      | Longitude used for the air-pollution request.           |
| `api`             | Yes      | API that produced the response.                         |
| `endpoint`        | Yes      | Endpoint used for the request.                          |
| `start`           | Yes      | Start of the requested historical time window.          |
| `end`             | Yes      | End of the requested historical time window.            |
| `retrieved_at`    | Yes      | UTC time when the API response was received.            |
| `run_id`          | Yes      | Identifier for the pipeline run.                        |
| `pipeline_run_id` | Yes      | Identifier connecting the response to the pipeline run. |
| `status`          | Yes      | HTTP/request status of the response.                    |
| `payload`         | Yes      | Original OpenWeather air-pollution API response.        |

The raw payload remains unchanged by Extract and is available to Transform under `payload`.

### Expected Raw Payload

For a successful air-pollution response, the relevant structure is:

```json
{
  "coord": {
    "lon": -122.4194,
    "lat": 37.7749
  },
  "list": [
    {
      "dt": 1720000000,
      "main": {
        "aqi": 2
      },
      "components": {
        "co": 201.94,
        "no": 0.0,
        "no2": 1.2,
        "o3": 68.6,
        "so2": 0.6,
        "pm2_5": 4.3,
        "pm10": 5.1,
        "nh3": 0.12
      }
    }
  ]
}
```

The `list` array may contain multiple observations for the requested time window.

Transform must process each observation independently.

---


## 2. Extraction Context

The Transform stage must retain the context from the `RawResponse` when creating output records.

The following fields are carried from the raw response to every transformed record created from that response:

* `city_id`
* `city_name`
* `country_code`
* `state_code`, when available
* `lat`
* `lon`
* `run_id`
* `pipeline_run_id`

The API metadata and retrieval information remain part of the raw response context and are not required to be repeated on every clean observation record unless a downstream requirement is added later.

`city_id` is the primary location identifier used by Transform. The transformed record must not depend on the city name being unique.

---

## 3. Output Granularity

The Transform stage returns **one record per city per observation timestamp**.

The OpenWeather response contains multiple observations inside `payload.list`. Each element of `payload.list` becomes one transformed application record.

Conceptually:

```text
RawResponse
└── payload.list
    ├── observation 1 → transformed record 1
    ├── observation 2 → transformed record 2
    ├── observation 3 → transformed record 3
    └── ...
```

The expected output granularity is therefore:

> **One air-quality observation for one city at one timestamp.**

The target is commonly described as "one row per city per hour" because the historical OpenWeather data is expected to provide hourly observations. The Transform contract uses the more general **city + observation timestamp** definition so it does not depend on a storage-specific row definition or assume a particular sampling interval.

Transform does not aggregate multiple observations into daily or weekly records.

---

## 4. Raw-to-Clean Field Mapping

Each observation in `payload.list` is flattened into a clean application record.

| Raw field                          | Clean field       | Description                                        |
| ---------------------------------- | ----------------- | -------------------------------------------------- |
| `payload.list[i].dt`               | `observed_at`     | Observation timestamp converted to a UTC datetime. |
| `payload.list[i].main.aqi`         | `aqi`             | OpenWeather Air Quality Index value.               |
| `payload.list[i].main.aqi`         | `aqi_label`        | Human-readable AQI category: Good, Fair, Moderate, Poor, or Very Poor. |
| `payload.list[i].components.co`    | `co`              | Carbon monoxide measurement.                       |
| `payload.list[i].components.no`    | `no`              | Nitrogen monoxide measurement.                     |
| `payload.list[i].components.no2`   | `no2`             | Nitrogen dioxide measurement.                      |
| `payload.list[i].components.o3`    | `o3`              | Ozone measurement.                                 |
| `payload.list[i].components.so2`   | `so2`             | Sulphur dioxide measurement.                       |
| `payload.list[i].components.pm2_5` | `pm2_5`           | PM2.5 measurement.                                 |
| `payload.list[i].components.pm10`  | `pm10`            | PM10 measurement.                                  |
| `payload.list[i].components.nh3`   | `nh3`             | Ammonia measurement.                               |
| `RawResponse.city_id`              | `city_id`         | Stable configured city identifier.                 |
| `RawResponse.city_name`            | `city_name`       | City name from the extraction context.             |
| `RawResponse.country_code`         | `country_code`    | Country code from the extraction context.          |
| `RawResponse.state_code`           | `state_code`      | State/region code when available.                  |
| `RawResponse.lat`                  | `lat`             | Latitude used for extraction.                      |
| `RawResponse.lon`                  | `lon`             | Longitude used for extraction.                     |
| `RawResponse.run_id`               | `run_id`          | Pipeline run identifier.                           |
| `RawResponse.pipeline_run_id`      | `pipeline_run_id` | Pipeline execution identifier.                     |

### Timestamp Handling

`dt` is the Unix timestamp supplied by OpenWeather.

Transform converts `dt` into `observed_at`, represented as a UTC datetime.

The city's configured timezone is not used to change the stored observation instant. It may be used later for presentation or local-time analysis.

---

## 5. Transform Output

The Transform stage returns a collection of clean air-quality observation records.

Conceptually:

```text
Transform(RawResponse)
        ↓
[
  AirQualityRecord,
  AirQualityRecord,
  AirQualityRecord,
  ...
]
```

Each output record contains the location context and exactly one observation's measurements.

### Output Record

```json
{
  "city_id": "us-san-francisco-ca",
  "city_name": "San Francisco",
  "country_code": "US",
  "state_code": "CA",
  "lat": 37.7749,
  "lon": -122.4194,
  "observed_at": "2024-07-03T12:26:40Z",
  "aqi": 2,
  "aqi_label": "Fair",
  "co": 201.94,
  "no": 0.0,
  "no2": 1.2,
  "o3": 68.6,
  "so2": 0.6,
  "pm2_5": 4.3,
  "pm10": 5.1,
  "nh3": 0.12,
  "run_id": "run-2024-07-03-001",
  "pipeline_run_id": "pipeline-2024-07-03-001"
}
```

This is an **application-level transformed record**. It does not prescribe PostgreSQL column types, indexes, constraints, table names, or other storage details.

---

## 6. Transformation Rules

### 1. One observation becomes one record

Every element of `payload.list` produces one output record.

### 2. Flatten nested measurements

Nested fields under `main` and `components` are flattened into top-level clean fields.

### 3. Preserve location identity

The `city_id` from the extraction context is copied to every record generated from that response.

### 4. Preserve pipeline lineage

`run_id` and `pipeline_run_id` are copied to every transformed record so downstream processing can identify which pipeline execution produced the data.

### 5. Normalize observation timestamps

The Unix timestamp in `dt` is converted to a UTC datetime and stored as `observed_at`.

### 6. Do not modify the raw payload

Transform reads from the raw payload but does not modify the original raw response.

### 7. Do not aggregate observations

Transform does not calculate daily averages, hourly averages, or other aggregations. Each API observation remains an individual output record.

### 8. Do not define storage behavior

Transform does not determine how records are inserted, updated, indexed, or stored in PostgreSQL.

---

## 7. Invalid or Missing Data

The Transform stage should not silently invent values for missing measurements.

If a required structural field such as `payload.list` is missing or has an unexpected structure, the response cannot be transformed into observation records and should be treated as a transformation failure.

For an individual observation, missing measurement fields should be handled according to the validation rules established by the Transform implementation. Valid ranges and measurement units for pollutant fields are defined in `normalization-rules.md`. The Transform contract does not define database-level `NULL` constraints.

A failed transformation must retain enough context to identify:

* `city_id`
* `run_id`
* `pipeline_run_id`
* The affected raw response or observation

---

## 8. Transform Contract Summary

### Input

```text
RawResponse
├── location context
│   ├── city_id
│   ├── city_name
│   ├── country_code
│   ├── state_code
│   ├── lat
│   └── lon
├── API context
│   ├── api
│   ├── endpoint
│   ├── start
│   ├── end
│   ├── retrieved_at
│   ├── status
│   ├── run_id
│   └── pipeline_run_id
└── payload
    └── list[]
        └── air-quality observation
```

### Output

```text
AirQualityRecord[]
└── one record per city per observation timestamp
    ├── city identity
    ├── coordinates
    ├── observed_at
    ├── AQI
    ├── pollutant measurements
    └── pipeline lineage
```

The Transform stage therefore acts as the boundary between **Extract's API-shaped raw data** and **clean, observation-level application data** that can be consumed by the downstream Load/gold layer.
