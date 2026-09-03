# Environment Profiles Guide

This doc lists every environment variable the pipeline reads, where each one is safe to keep, and
how local runs versus scheduled/CI runs should be configured.

## Environment variables

### Application settings (`pipeline.common.config.Settings`)

These are loaded from a `.env` file or the process environment by `pydantic-settings`. See
`services/pipeline/src/pipeline/common/config.py`.

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `OPENWEATHER_API_KEY` | Yes, for any extract run | `""` | Secret. Used by `pipeline.extract.geocoding` and `pipeline.extract.openweather_air_pollution` to call the OpenWeather API. |
| `RAW_DIR` | No | `data/raw` | Local path for raw extract output. |
| `GOLD_DIR` | No | `data/gold` | Local path for gold dataset output. |
| `HISTORY_HOURS` | No | `24` | Hours of Air Pollution history to request per run. |
| `CITIES_SOURCE` | No | `file` | Where the city list comes from. |
| `CITIES_FILE` | No | `config/cities.json` | Used when `CITIES_SOURCE=file`. |

### Database connection

These are read directly from the process environment (not through `Settings`), so they must be
exported or present in `.env` regardless of which settings class picks them up.

| Variable | Required | Notes |
| --- | --- | --- |
| `DATABASE_URL` | Yes, for migrations and any DB-backed run | Read in `services/pipeline/alembic/env.py`. Format: `postgresql+psycopg://<user>:<password>@<host>:<port>/<db>`. |
| `TEST_DATABASE_URL` | Yes, for storage/integration tests | Points at a separate scratch database so tests never touch dev or prod data. No storage/integration tests exist in this repo yet — this documents the intended setup. |

## What's safe to commit

- `.env.example` — the repo's `.gitignore` explicitly un-ignores it (`!.env.example`). Keep it
  checked in, but only with placeholder values (e.g. `<username>`, `<password>`), never a real
  API key or a real database password.
- Documentation that references variable *names* (this file, `docs/setup/database_migrations.md`).

## What must stay out of the repository

- `.env` — already covered by `.gitignore` (`.env`, `.env.*`). Never commit real values for
  `OPENWEATHER_API_KEY`, `DATABASE_URL`, or `TEST_DATABASE_URL`.
- Any file containing a real OpenWeather API key or a database connection string with real
  credentials, even temporarily (scratch files, notebooks, logs pasted into a PR description).
- If a secret is committed by accident, treat it as compromised: rotate the API key /
  database password, then remove the file from history before considering the leak resolved —
  deleting the file in a new commit is not enough.

## Local runs

1. Copy `.env.example` to `.env` in the repo root and fill in real values:
   ```env
   OPENWEATHER_API_KEY=<your key>
   DATABASE_URL=postgresql+psycopg://<username>:<password>@localhost:5432/city_air_tracker
   TEST_DATABASE_URL=postgresql+psycopg://<username>:<password>@localhost:5432/city_air_tracker_test
   ```
2. Make sure PostgreSQL is running locally (see `docs/setup/database_migrations.md`).
3. Both `pydantic-settings` and Alembic's `env.py` automatically load values from `.env`, so no
   manual `export` is needed as long as commands are run from a directory where `.env` is
   discoverable (repo root). Note that Alembic commands themselves must be run from
   `services/pipeline/` (where `alembic.ini` lives) — see `docs/setup/database_migrations.md`.
4. Never point `DATABASE_URL` and `TEST_DATABASE_URL` at the same database — the test suite
   creates and drops schema objects.

## Scheduled / CI runs

Scheduled and CI runs must not rely on a checked-out `.env` file — inject the same variable names
as real environment variables from the platform's secret store instead:

- **GitHub Actions**: set `OPENWEATHER_API_KEY`, `DATABASE_URL`, and `TEST_DATABASE_URL` (as
  needed by the job) via `secrets.*` in the workflow's `env:` block, or via a Postgres service
  container's connection details for ephemeral test databases. Do not echo these values in logs.
- **Azure (or other managed hosting) for a future scheduled pipeline run**: set the same variable
  names in the service's application settings / Key Vault reference, not in a file shipped with
  the deployment. The pipeline code doesn't need to change between local and hosted runs — only
  where the values come from changes.

The current `python-quality-gates.yml` workflow only runs `compileall` and `pytest`; it does not
yet inject `DATABASE_URL` or `OPENWEATHER_API_KEY`. Once CI jobs need a real database (e.g. the
storage/integration tests), add a Postgres service container to that job and set
`TEST_DATABASE_URL` to point at it, following the same variable name used locally.
