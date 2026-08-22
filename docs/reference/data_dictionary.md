# Air Pollution Gold Data Dictionary

## Overview
This document defines the schema, data types, units, and transformation rules for the Gold analytical dataset (`air_pollution_gold`) produced by the transform stage from the OpenWeather Air Pollution API raw payload and execution context envelope.

---

## Field Specifications

| Field Name | Description | Data Type | Unit / Format | Source / Transformation Rule | Required / Optional | Example |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `observed_at` | Timestamp of the air quality observation | `datetime` | UTC, ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`) | `raw["dt"]` -> `datetime.fromtimestamp(dt, tz=timezone.utc)` | Required | `2026-08-15T12:00:00Z` |
| `city_id` | Business identifier configured for the city | `string` | Lowercase slug from config | Envelope context: `envelope.city_id` | Required | `sultan-us` |
| `city_name` | Display name of the city | `string` | UTF-8 text | Envelope context: `envelope.city_name` | Required | `Sultan` |
| `country_code` | ISO 3166-1 alpha-2 country code | `string` | ISO 3166-1 alpha-2 (Uppercase) | Envelope context: `envelope.country_code`. Note: current `normalize_text` (PR #14) preserves casing as-is — uppercasing is not yet implemented and needs adding if this rule stays. | Required | `US` |
| `state_code` | State/province/region code, when available | `string` | ISO 3166-2 subdivision code (Uppercase) or absent | Envelope context: `envelope.state_code` | Optional | `WA` |
| `lat` | Geographical latitude of measurement/request location | `float` | Decimal degrees (`-90.0` to `90.0`) | Envelope context: `envelope.lat` (Single source of truth) | Required | `47.8623` |
| `lon` | Geographical longitude of measurement/request location | `float` | Decimal degrees (`-180.0` to `180.0`) | Envelope context: `envelope.lon` (Single source of truth) | Required | `-121.8157` |
| `aqi` | Qualitative Air Quality Index level (1=Good, 2=Fair, 3=Moderate, 4=Poor, 5=Very Poor) | `integer` | Categorical integer (`1` to `5`) | `raw["main"]["aqi"]` | Required | `2` |
| `aqi_label` | Human-readable AQI category | `string` | One of: Good, Fair, Moderate, Poor, Very Poor | Derived from `aqi` via the `_AQI_LABELS` lookup dict in `aqi_label()` (`services/pipeline/src/pipeline/transform/operations.py`) | Required | `Fair` |
| `co` | Concentration of Carbon monoxide | `float` | ug/m3 | `raw["components"]["co"]` | Optional | `201.94` |
| `no` | Concentration of Nitrogen monoxide | `float` | ug/m3 | `raw["components"]["no"]` | Optional | `0.01` |
| `no2` | Concentration of Nitrogen dioxide | `float` | ug/m3 | `raw["components"]["no2"]` | Optional | `3.77` |
| `o3` | Concentration of Ozone | `float` | ug/m3 | `raw["components"]["o3"]` | Optional | `68.66` |
| `so2` | Concentration of Sulphur dioxide | `float` | ug/m3 | `raw["components"]["so2"]` | Optional | `0.64` |
| `pm2_5` | Concentration of fine particulate matter (aerodynamic diameter <= 2.5 um) | `float` | ug/m3 | `raw["components"]["pm2_5"]` | Optional | `8.45` |
| `pm10` | Concentration of coarse particulate matter (aerodynamic diameter <= 10 um) | `float` | ug/m3 | `raw["components"]["pm10"]` | Optional | `12.10` |
| `nh3` | Concentration of Ammonia | `float` | ug/m3 | `raw["components"]["nh3"]` | Optional | `0.85` |
| `run_id` | Identifier for the pipeline run | `string` | `run-YYYY-MM-DD-NNN` | Envelope context: `envelope.run_id` | Required | `run-2026-08-15-001` |
| `pipeline_run_id` | Identifier connecting the response to the pipeline execution run | `string` | `pipeline-YYYY-MM-DD-NNN` | Envelope context: `envelope.pipeline_run_id` | Required | `pipeline-2026-08-15-001` |
| `retrieved_at` | Timestamp when the raw payload was fetched from the API | `datetime` | UTC, ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`) | Envelope context: `envelope.retrieved_at` | Not yet implemented — excluded from Extraction Context per transform-input-output-contract.md §2; needs a decision (add to Transform output, or drop from Gold) | `2026-08-15T23:05:12Z` |

---

## Dataset Scope & Filtering Rules

* **Gold Table Eligibility:** The Gold analytical dataset only contains successfully extracted and parsed observation records (`status == "ok"`).
* **Handling of `empty` and `error` Records:** Raw envelopes with status `"empty"` (no observations available in requested time window) or `"error"` (HTTP/network/parsing failures) are filtered out during the transformation stage and tracked via pipeline run metadata/logs. They do not produce rows with `NULL` metrics in Gold.
* **Component Completeness & API Contract:** Pollutant metrics (`co` through `nh3`) are Optional in the Gold schema. The current transform stage (see `normalization_rules.md`, PR #14) already sets a component to `NULL` when the key is missing or the value is negative — this is existing behavior, not a hypothetical future case.

---

## Primary Key & Grain *(Proposed — to be confirmed in AIR-19)*

* **Dataset Grain:** One row per city per observation timestamp.
* **Composite Primary Key / Deduplication Key:** `(city_id, observed_at)`

---

## Quality Rules & Invariants *(Proposed — to be confirmed in AIR-19)*

* **Temporal Integrity:** `observed_at <= retrieved_at` (enforceable only once `retrieved_at` is added to the Transform output — see note above).
* **Value Bounds:**
  * `aqi` must be one of `[1, 2, 3, 4, 5]`.
  * All chemical pollutant concentrations (`co`, `no`, `no2`, `o3`, `so2`, `pm2_5`, `pm10`, `nh3`) must be `>= 0.0` when present (or `NULL`).
* **Coordinate Consistency:** `lat` between `-90.0` and `90.0`, `lon` between `-180.0` and `180.0`.