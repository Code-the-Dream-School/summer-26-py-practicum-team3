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

The record is inserted.

## Updated Record

A record is considered an update when an existing Gold record has the same
`city_id` and `observed_at`.

The incoming transformed record replaces the existing record's values.

## Repeated Pipeline Runs

If a repeated or subsequent pipeline run produces an observation with the
same `city_id` and `observed_at`, the existing record is updated rather
than a duplicate record being created.

## Database Constraint

The database must enforce uniqueness on:

`(city_id, observed_at)`

This allows the PostgreSQL upsert operation to use
`ON CONFLICT (city_id, observed_at)` as its conflict target.
