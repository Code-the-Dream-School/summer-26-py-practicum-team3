# City Air Tracker Database Schema

## Overview

This document defines the PostgreSQL schema for the City Air Tracker pipeline. The schema is based on the Sprint 2 raw response contract, Sprint 3 transform data dictionary, city input contract, and pipeline run tracking requirements.

The City Air Tracker PostgreSQL database contains five tables:

| Table                         | Purpose                                                     |
| ----------------------------- | ----------------------------------------------------------- |
| `cities`                      | Stores configured cities and location reference data        |
| `pipeline_runs`               | Tracks each pipeline execution                              |
| `raw_geocoding_responses`     | Stores raw geocoding API responses                          |
| `raw_air_pollution_responses` | Stores raw air pollution API responses                      |
| `air_pollution_gold`          | Stores transformed and validated air pollution observations |

---

## Database Schema

### `cities`

Stores configured city and location reference information.

| Column         | PostgreSQL Type | Required | Key / Constraint | Description                         |
| -------------- | --------------- | -------: | ---------------- | ----------------------------------- |
| `city_id`      | `TEXT`          |      Yes | **PK**           | Stable identifier for the city      |
| `city_name`    | `TEXT`          |      Yes | —                | City name                           |
| `country_code` | `CHAR(2)`       |      Yes | —                | ISO country code                    |
| `state_code`   | `TEXT`          |       No | —                | State/province code when applicable |
| `timezone`     | `TEXT`          |      Yes | —                | IANA timezone                       |
| `active`       | `BOOLEAN`       |      Yes | No default       | Whether the city is active          |

**Unique constraint:** `city_name`, `country_code`, and `state_code`, treating a missing `state_code` as an empty value.

---

### `pipeline_runs`

Tracks each execution of the pipeline.

| Column               | PostgreSQL Type | Required | Key / Constraint                 | Description                              |
| -------------------- | --------------- | -------: | -------------------------------- | ---------------------------------------- |
| `pipeline_run_id`    | `BIGSERIAL`     |      Yes | **PK**                           | Database identifier for the pipeline run |
| `run_id`             | `TEXT`          |      Yes | **UNIQUE**                       | Pipeline run identifier                  |
| `source`             | `TEXT`          |      Yes | —                                | Pipeline/source name                     |
| `history_hours`      | `INTEGER`       |      Yes | `> 0`                            | Number of historical hours requested     |
| `window_start_utc`   | `TIMESTAMPTZ`   |      Yes | —                                | Start of requested data window           |
| `window_end_utc`     | `TIMESTAMPTZ`   |      Yes | `>= window_start_utc`            | End of requested data window             |
| `status`             | `TEXT`          |      Yes | `running`, `succeeded`, `failed` | Current pipeline status                  |
| `city_count`         | `INTEGER`       |      Yes | `>= 0`                           | Number of cities processed               |
| `raw_response_count` | `INTEGER`       |      Yes | `>= 0`                           | Number of raw responses stored           |
| `gold_row_count`     | `INTEGER`       |      Yes | `>= 0`                           | Number of transformed rows               |
| `error_message`      | `TEXT`          |       No | —                                | Error information when a run fails       |
| `finished_at`        | `TIMESTAMPTZ`   |       No | —                                | Time the pipeline finished               |
| `created_at`         | `TIMESTAMPTZ`   |      Yes | Default `NOW()`                  | Time the pipeline run was created        |

---

### `raw_geocoding_responses`

Stores raw responses from the geocoding API, including the location context and coordinates produced by the geocoding step.

Repeated requests are retained rather than overwritten.

| Column                      | PostgreSQL Type    | Required | Key / Constraint                         | Description                                     |
| --------------------------- | ------------------ | -------: | ---------------------------------------- | ----------------------------------------------- |
| `raw_geocoding_response_id` | `BIGSERIAL`        |      Yes | **PK**                                   | Unique identifier for the stored response       |
| `pipeline_run_id`           | `BIGINT`           |      Yes | **FK** → `pipeline_runs.pipeline_run_id` | Pipeline run that generated the response        |
| `city_id`                   | `TEXT`             |      Yes | **FK** → `cities.city_id`                | Stable city identifier                          |
| `city_name`                 | `TEXT`             |      Yes | —                                        | City name included in the response context      |
| `country_code`              | `CHAR(2)`          |      Yes | —                                        | ISO country code                                |
| `state_code`                | `TEXT`             |       No | —                                        | State/province code when available              |
| `latitude`                  | `DOUBLE PRECISION` |       No | `-90–90`                                 | Latitude returned by the API or fallback table  |
| `longitude`                 | `DOUBLE PRECISION` |       No | `-180–180`                               | Longitude returned by the API or fallback table |
| `coordinate_source`         | `TEXT`             |      Yes | `geocoded`, `fallback`, `absent`         | Source of the coordinates                       |
| `endpoint`                  | `TEXT`             |      Yes | —                                        | API endpoint used                               |
| `retrieved_at`              | `TIMESTAMPTZ`      |      Yes | —                                        | UTC time when the response was received         |
| `http_status`               | `INTEGER`          |       No | `100–599`                                | HTTP response status                            |
| `payload`                   | `JSONB`            |      Yes | —                                        | Original raw API response                       |

**Uniqueness:** No request-level uniqueness constraint is applied because repeated API requests must be retained.

**Coordinate fields:** `latitude` and `longitude` are nullable because a geocoding response can have no coordinates. `coordinate_source` records whether coordinates came from the API, the fallback coordinate table, or were absent.

---
### `raw_air_pollution_responses`

Stores raw responses from the air pollution API, including the city context, coordinates used for the request, and requested time window.

Repeated requests are retained rather than overwritten.

| Column                          | PostgreSQL Type    | Required | Key / Constraint                         | Description                                |
| ------------------------------- | ------------------ | -------: | ---------------------------------------- | ------------------------------------------ |
| `raw_air_pollution_response_id` | `BIGSERIAL`        |      Yes | **PK**                                   | Unique identifier for the stored response  |
| `pipeline_run_id`               | `BIGINT`           |      Yes | **FK** → `pipeline_runs.pipeline_run_id` | Pipeline run that generated the response   |
| `city_id`                       | `TEXT`             |      Yes | **FK** → `cities.city_id`                | Stable city identifier                     |
| `city_name`                     | `TEXT`             |      Yes | —                                        | City name included in the response context |
| `country_code`                  | `CHAR(2)`          |      Yes | —                                        | ISO country code                           |
| `state_code`                    | `TEXT`             |       No | —                                        | State/province code when available         |
| `latitude`                      | `DOUBLE PRECISION` |      Yes | `-90–90`                                 | Latitude used for the API request          |
| `longitude`                     | `DOUBLE PRECISION` |      Yes | `-180–180`                               | Longitude used for the API request         |
| `start`                         | `TIMESTAMPTZ`      |      Yes | —                                        | Start of the requested UTC time window     |
| `end`                           | `TIMESTAMPTZ`      |      Yes | `>= start`                               | End of the requested UTC time window       |
| `endpoint`                      | `TEXT`             |      Yes | —                                        | API endpoint used                          |
| `retrieved_at`                  | `TIMESTAMPTZ`      |      Yes | —                                        | UTC time when the response was received    |
| `http_status`                   | `INTEGER`          |       No | `100–599`                                | HTTP response status                       |
| `payload`                       | `JSONB`            |      Yes | —                                        | Original raw API response                  |

**Uniqueness:** No request-level uniqueness constraint is applied because repeated API requests must be retained.

**Location fields:** `latitude` and `longitude` record the coordinates actually used in the air pollution API request, making the stored response self-describing without requiring a lookup against the geocoding response.

**Request window:** `start` and `end` record the UTC time range requested for the API call.

**Timestamp:** `retrieved_at` is supplied by the extract layer and represents the time the response was received. It does not use a database default because database insertion time may differ from response-retrieval time.

### `air_pollution_gold`

Stores transformed and validated air pollution observations.

**Grain:** One row per city per observation.

| Column         | PostgreSQL Type    | Required | Key / Constraint              | Description                           |
| -------------- | ------------------ | -------: | ----------------------------- | ------------------------------------- |
| `city_id`      | `TEXT`             |      Yes | **PK, FK** → `cities.city_id` | City associated with the observation  |
| `observed_at`  | `TIMESTAMPTZ`      |      Yes | **PK**                        | Time of the air pollution observation |
| `aqi`          | `INTEGER`          |      Yes | `1–5`                         | Air Quality Index                     |
| `pm2_5`        | `DOUBLE PRECISION` |      Yes | `>= 0`                        | PM2.5 concentration                   |
| `pm10`         | `DOUBLE PRECISION` |      Yes | `>= 0`                        | PM10 concentration                 
   |
| `co`           | `DOUBLE PRECISION` |      Yes | `>= 0`                        | Carbon monoxide concentration         |
| `no2`          | `DOUBLE PRECISION` |      Yes | `>= 0`                        | Nitrogen dioxide concentration        |
| `o3`           | `DOUBLE PRECISION` |      Yes | `>= 0`                        | Ozone concentration                   |
| `so2`          | `DOUBLE PRECISION` |      Yes | `>= 0`                        | Sulfur dioxide concentration          |
| `latitude`     | `DOUBLE PRECISION` |      Yes | `-90–90`                      | Geographic latitude                   |
| `longitude`    | `DOUBLE PRECISION` |      Yes | `-180–180`                    | Geographic longitude                  |
| `retrieved_at` | `TIMESTAMPTZ`      |       No | —                             | Time the data was retrieved           |

**Primary key:** `(city_id, observed_at)`

`retrieved_at` is nullable because it is not currently produced by the transform output and is subject to confirmation in AIR-19.

---

