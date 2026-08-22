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
