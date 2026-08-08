# City Input Contract

## Purpose

The City Input Contract defines all upstream inputs required by the extract layer of the City Air Tracker pipeline.  
It covers inputs for **City configuration** — the list of cities the pipeline tracks. It allows the pipeline to geocode each city and, from there, request historical air-pollution data for it. 

The air-pollution data input itself (the raw measurements retrieved per city from OpenWeather) is covered separately in `air-quality-input-contract.md`, not in this
document.

---

## 1. City Configuration Contract

### Geographic Scope 
This version of the pipeline is **intended to operate on cities within the United States**. 
This reflects the current project scope, not a permanent limitation.

This scope is a stated intent only and is **not currently enforced** by any validation  rule below. A `country_code` other than `"US"` is not rejected at this time — Rule 4
only checks that a code is a valid ISO 3166-1 alpha-2 code, not that it equals `"US"`.
If US-only should be enforced, that will need to be added as an explicit rule in a  future revision.

### Required Fields

| Field    | Type         | Required | Description                                                                                                                                                                                                                                                                                          |
|----------|--------------|----------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `city_name` | string | Yes      | Common name of the city, as it would be searched (e.g. "Portland"). Must not be empty or whitespace-only. Required for geocoding.                                                                                                                                                                    |
| `country_code`| string | Yes      | ISO 3166-1 alpha-2 country code (e.g. "US"). Used to disambiguate cities that share a name across countries.                                                                                                                                                                                         |
| `state_code` | string | No       | ISO 3166-2 state/province/region code (e.g. "CA") when applicable. Optional for countries without states.                                                                                                                                                                                            |
| `city_id` | string | Yes      | A short, stable, unique identifier for this city within the configuration (e.g., `us-portland-or`). Used internally throughout the pipeline (raw storage, transform, gold dataset) to track the city independently of how its name or geocoded coordinates might change. See `city_id` Format below. |
| `timezone` | string | Yes      | IANA format (e.g. "America/Los_Angeles"). Used later to normalize timestamps in pollution data.                                                                                                                                                                                                      |
| `active` | boolean | Yes      | Indicates whether the pipeline should include this city in extraction runs. Must be explicitly set to `true` or `false` on every entry.                                                                                                                                                              |

### Field notes

- **`city_name`** is the human-facing label and the string sent to the geocoding step.
  It is not assumed to be unique on its own.
- **`country_code`** is required on every entry, even when a city name seems unambiguous
  today — new entries can introduce collisions later, and requiring it consistently
  avoids special-casing.
- **`state_code`** is optional but strongly recommended whenever it would help
  disambiguate (e.g. "Portland, US, OR" vs. "Portland, US, ME"). Its absence is not an
  error on its own.
- **`city_id`** is set once and does not change, even if `city_name` is later corrected
  or reformatted. Downstream layers (raw storage, transform, gold dataset) key on
  `city_id`, not on name/country/state.
- **`timezone`** will be used to normalize timestamps in the pollution data.
  The pipeline stage where that normalization happens (Extract vs. Transform) has not
  been decided yet — this contract only guarantees the field is present and valid on
  the city entry, not when or where it gets applied.
- **`active`** controls whether a city is picked up by an extraction run without
  requiring the entry to be deleted from the configuration — see Rule 5.

  > **Note:** `active` is required with no default so that adding a city always means an explicit decision, not an implicit one. This matters even for bulk import: 
  a default would let a single bad import script silently flip many cities to active (or inactive) at once, 
  burning API quota and populating the dashboard with entries no one deliberately chose. 

### Fields explicitly not part of this contract

- **`latitude`** and **`longitude`** are produced by the extract stage and are **not part of this contract**.

---

### `city_id` Format

`city_id` is built as `{country_code}-{city_name_slug}-{state_code}`, all lowercase,
hyphen-separated.

**When `state_code` is present:**
`{country_code}-{city_name_slug}-{state_code}` → `us-portland-or`

**When `state_code` is absent:**
`state_code` is simply dropped from the pattern (not replaced with a placeholder):
`{country_code}-{city_name_slug}` → `fr-paris`

**Slugifying `city_name`:**
- Lowercase the name.
- Replace spaces with hyphens.
- Drop all other punctuation entirely (periods, apostrophes, commas) — do not replace
  it with a hyphen or any other character.
- Collapse repeated hyphens into one.

Examples:

| `city_name`      | `country_code` | `state_code` | slug           | `city_id`             |
|-------------------|----------------|--------------|----------------|------------------------|
| Portland          | US             | OR           | `portland`     | `us-portland-or`       |
| St. Louis         | US             | MO           | `st-louis`     | `us-st-louis-mo`       |
| Coeur d'Alene      | US             | ID           | `coeur-dalene` | `us-coeur-dalene-id`   |
| Paris             | FR             | —            | `paris`        | `fr-paris`             |


---

## Valid Example (City Configuration)

```json
{
  "city_id" : "us-san-francisco-ca",
  "city_name": "San Francisco",
  "country_code": "US",
  "state_code": "CA",
  "timezone": "America/Los_Angeles",
  "active": true
}
```

## Rules for Missing or Invalid Values

### 1. Required fields
- **Missing `city_name`, `country_code`, `city_id`, `timezone`, or `active` ** 
   → The entry is invalid. It must be rejected and excluded from the run. It must not be
   silently skipped — the rejection is logged with the entry's position/index in the
   configuration so it can be found and fixed.
- **Empty or whitespace-only string in any required field**
   Treated the same as a missing value (see rule above).

### 2. Optional fields
- **Missing `state_code`**
   → Not an error. The entry is processed as-is; geocoding falls back to `city_name` +
   `country_code` only.

### 3. Duplicate identifiers
- **Duplicate `city_id`**
   → Invalid configuration. The whole configuration load fails rather than picking one
   of the duplicates arbitrarily, since a silent choice could point later pipeline
   layers at the wrong city's data.

### 4. Invalid codes
- **Invalid `country_code` (not a recognized ISO 3166-1 alpha-2 code)**
   → The entry is rejected, for the same reason as a missing field.
- **Invalid `timezone` (not a valid IANA identifier)**  
  → The entry is rejected

### 5. Active flag
- **Missing `active`** 
  → The entry is invalid and is rejected, same as Rule 1.
- **Invalid `active` (not boolean)**  
  → The entry is rejected.

### 6. Geocoding failures
- **Geocoding failure (city not found by the API)**
   Out of scope for this contract. That is an Extract-layer runtime concern, not a
   configuration validity concern — the entry may be well-formed and still fail to
   geocode. How that's handled will be defined when the Extract layer is implemented.

### 7. General rule
Invalid city records must be logged and excluded from extraction.

## Out of Scope for This Contract

- Storage format of the city configuration (CSV/JSON/etc.)
- Loading/parsing implementation
- Validation code
- Geocoding retry or error-handling behavior
- The pipeline stage where `timezone` normalization is actually applied
- Anything downstream of Extract (Transform, Load)

## Open Questions

- Should there be a maximum number of cities per run?
- Do we need a way to temporarily disable a city entry without deleting it?
- Should the US-only geographic scope be enforced as a validation rule in a future
  revision, or does it remain intent-only indefinitely? 
