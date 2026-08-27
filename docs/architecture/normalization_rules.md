# Normalization Rules - Air Pollution Transform


**API:** OpenWeather Air Pollution History (`/data/2.5/air_pollution/history`)
**Raw input:** `RawResponse` as defined in `transform-input-output-contract.md`
**Output granularity:** one `AirQualityRecord` row per `(city_id, observed_at)`
**Scope:** these rules apply to a `RawResponse` that already carries a resolved `city_id`. If city_id is missing at this stage, the record is dropped.

## 1. Pre-Processing: Response-Level Gate

Before any field-level rule runs, the transform checks `RawResponse.status`:

| `status` | Handling                                                                                                   |
|----------|------------------------------------------------------------------------------------------------------------|
| `"ok"` | Proceed with field-level normalization below.                                                              |
| `"empty"` | Valid response with no observations; not a data-quality problem. Skipped, logged at info level.            |
| `"error"` | Request/response failure. Skipped, logged with available context (`city_id`, `run_id`, `pipeline_run_id`). |

---

## 2. Field-Level Normalization Rules

Each row corresponds to a field on the `AirQualityRecord` output, per `transform-input-output-contract.md` Section 5.

| #  | Rule                               | Field(s)                                               | Handling                                                                                                                                                                           |
|----|------------------------------------|--------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1  | Extract response status gate       | `status`                                               | Only "ok" responses are transformed. `"empty"` and `"error"` are both skipped before field-level rules run.                                                                        |
| 2  | Missing city identity              | `city_id`                                              | Required. Record dropped if missing.                                                                                                                                               |
| 3  | Timestamp normalization            | `dt` -> `observed_at`                                  | Unix UTC seconds converted to a timezone-aware UTC `datetime`. Required field -- record dropped if `dt` is missing/unparsable.                                                     |
| 4  | Coordinate type & range            | `lat`, `lon`                                           | Cast to float, validated within ±90/±180. Required; dropped if invalid.                                                                                                            |
| 5  | AQI typing                         | `aqi`                                                  | Cast to int, must be 1-5. Required; dropped if missing or out of range.                                                                                                            |
| 6  | Pollutant unit and type            | `co`, `no`, `no2`, `o3`, `so2`, `pm2_5`, `pm10`, `nh3` | Already µg/m³ -- no unit conversion. Cast to float, rounded to 2 decimals. Optional fields.                                                                                        |
| 7  | Invalid pollutant reading          | same as #6                                             | Negative value is physically impossible -> set to `NULL`. Record is kept.                                                                                                          |
| 8  | Missing pollutant reading          | same as #6                                             | Missing key -> `NULL`. Record is kept.                                                                                                                                             |
| 9  | Text field cleanup                 | `city_name`, `country_code`, `state_code`              | Whitespace-stripped, empty string -> `NULL`. Casing preserved. `state_code` is optional; its absence is not an error.                                                              |
| 10 | Duplicate observations             | `city_id` + `observed_at`                              | Composite key. When city/timestamp duplicates exist, keep the record with the higher `pipeline_run_id` (string) and drop the others.                                                  |
| 11 | Pipeline lineage                   | `run_id`, `pipeline_run_id`                            | Passed through unchanged -- no normalization applied.                                                                                                                              |
| 12 | Retrieval timestamp                | `retrieved_at`                                         | Passed through unchanged -- no normalization applied.                                                                                                                              |
| 13 | AQI Label  | `aqi_label`                                            | Maps `aqi` values (1–5) to OpenWeather categories: Good/Fair/Moderate/Poor/Very Poor. Provides a human-readable AQI category for dashboards without re‑implementing the mapping.   |

## Sprint 4 handoff
This rule set enforces required-field rules (drop invalid/incomplete records) and type/range/duplicate cleanup, on top of the shape defined in
`transform-input-output-contract.md`. The gold table should still declare `NOT NULL` on `city_id`, `observed_at`, `lat`, `lon`, `aqi`, `retrieved_at`, 
a `UNIQUE (city_id, observed_at)` constraint, and a `city_id` foreign key -- a second line of defense if invalid data ever reaches the DB another way.
