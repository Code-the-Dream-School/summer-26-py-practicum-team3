# Record Identification and Upsert Rules

## Air-Quality Observation Records

Air-quality observations are uniquely identified by the combination of:

- `city_id`
- `observed_at`

This matches the Transform contract's defined grain of one air-quality
observation for one city at one observation timestamp.

## New Record

A record is considered new when no existing Gold record has the same
`city_id` and `observed_at`.

The record is inserted into `air_pollution_gold`.

## Updated Record & Conflict Resolution

A record is considered an update when an existing Gold record in the database
shares the same `(city_id, observed_at)`.

The incoming transformed record updates the existing record **only if** the incoming
record has a strictly higher pipeline execution identifier:

```sql
ON CONFLICT (city_id, observed_at)
DO UPDATE SET ...
WHERE EXCLUDED.pipeline_run_id > air_pollution_gold.pipeline_run_id;