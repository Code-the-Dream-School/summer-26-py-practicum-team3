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
