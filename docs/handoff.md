# City Air Tracker — handoff

This document is written for someone who did not build the project. It covers what
exists, what it needs in order to run, how to walk through it end to end, and what
was left unfinished.

Companion documents are listed under [Where to look next](#where-to-look-next).
For a two-minute overview, start with the [root README](../README.md).

---

## 1. What the project does

City Air Tracker is a batch ETL pipeline plus a read-only dashboard.

For a configured list of cities it:

1. **Extracts** — geocodes each city to lat/lon through the OpenWeather Geocoding
   API, then pulls historical air-pollution readings from the OpenWeather Air
   Pollution API. Raw API responses are persisted before anything is derived from them.
2. **Transforms** — normalizes those responses into one clean row per city per
   observation timestamp, including the OpenWeather AQI value (1–5) and its label.
3. **Loads** — upserts the result into the `air_pollution_gold` table in PostgreSQL.
   A Parquet copy is written alongside it on a best-effort basis.
4. **Serves** — a Streamlit dashboard reads `air_pollution_gold` directly and shows
   current conditions per city and history over time.

Every run is recorded in a `pipeline_runs` table, so run history survives across
invocations and a run can be replayed from its stored raw responses without
calling the API again.

**There is no HTTP API and no React front end.** The original starter README
described one; the team built a Streamlit dashboard that queries PostgreSQL
directly instead. Anything you read elsewhere in this repository about a
"Python API" or "React dashboard" is stale.

---

## 2. Current status

| Area | State |
| --- | --- |
| Extract (geocoding + air pollution) | Working |
| Transform / normalization | Working |
| Load into PostgreSQL | Working |
| Parquet export | Working, best-effort — a failure is logged, not fatal |
| Run tracking + replay | Working |
| Scheduled runs (GitHub Actions, daily) | Working |
| Dashboard — Summary page | Working |
| Dashboard — Compare page | Working |
| Dashboard — City detail page | **Not built** (ticket AIR-35) |
| Azure Blob upload | **Not built** — `azure_blob_path` is always `null` |
| HTTP API / React front end | **Not built, and not planned** |

---

## 3. Runtime configuration

All settings are read from environment variables, or from a `.env` file **in the
directory the process is started from**. In practice that means
`services/pipeline/.env`, because every command below is run from
`services/pipeline`. This trips people up: the example file lives at the
repository root, but the file that is actually read is the one inside
`services/pipeline`.

```shell
cp .env.example services/pipeline/.env   # then edit it
```

### Variables

| Variable | Required | Default | What it does |
| --- | --- | --- | --- |
| `OPENWEATHER_API_KEY` | Yes, for live runs | — | API key for the OpenWeather geocoding and air-pollution endpoints. Free tier is enough. |
| `DATABASE_URL` | Yes | — | PostgreSQL connection string. Use the SQLAlchemy form, e.g. `postgresql+psycopg://user:password@localhost:5432/city_air_tracker`. Alembic and the pipeline use it as-is; the dashboard strips the `+psycopg` suffix itself, because raw psycopg does not accept it. |
| `TEST_DATABASE_URL` | Only for DB-backed tests | — | Points at a separate database, e.g. `city_air_tracker_test`. When unset, the integration tests that need a real database are skipped rather than failed. |
| `LOG_LEVEL` | No | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `HISTORY_HOURS` | No | `24` | How far back a run pulls readings. |
| `CITIES_SOURCE` | No | `file` | Where the city list comes from. |
| `CITIES_FILE` | No | `config/cities.json` | Path to the city list, relative to `services/pipeline`. |
| `RAW_DIR` | No | `data/raw` | Local directory for raw artifacts. |
| `GOLD_DIR` | No | `data/gold` | Local directory for the Parquet copy of the gold dataset. |

`OPENWEATHER_API_KEY` and `DATABASE_URL` are secrets. `.env` is gitignored; keep it
that way. For scheduled runs both are supplied as GitHub Actions repository secrets.

### Ports

| Service | Port | Notes |
| --- | --- | --- |
| PostgreSQL | `5432` | Standard local default. If yours differs, change it in `DATABASE_URL`. |
| Streamlit dashboard | `8501` | Streamlit's default. Override with `--server.port <n>`. |

Nothing else listens on a port. There is no API server.

### Which cities are processed

`services/pipeline/config/cities.json` — a list of objects with `city_id`,
`city_name`, `country_code`, optional `state_code`, `timezone` and `active`.
Only cities with `"active": true` are processed and shown on the dashboard.

---

## 4. First-time setup

Prerequisites: Python 3.12 or newer, a running PostgreSQL server, and an
OpenWeather API key.

```shell
git clone https://github.com/Code-the-Dream-School/summer-26-py-practicum-team3.git
cd summer-26-py-practicum-team3

python -m venv services/pipeline/venv
source services/pipeline/venv/bin/activate      # Windows: services\pipeline\venv\Scripts\activate
pip install -r requirements.txt

cp .env.example services/pipeline/.env          # then fill in the two required values

createdb city_air_tracker
cd services/pipeline
alembic upgrade head
```

`alembic upgrade head` creates all five tables: `cities`, `pipeline_runs`,
`raw_geocoding_responses`, `raw_air_pollution_responses` and `air_pollution_gold`.
See [`setup/database_migrations.md`](setup/database_migrations.md) for rollbacks
and for writing new migrations.

---

## 5. Runbook — local walkthrough

Run everything below from `services/pipeline` with the virtualenv active. This is
the sequence to follow when demonstrating the project.

### Step 1 — confirm the database is reachable

```shell
python run_pipeline.py db
```

Expected: connection status plus a row count per table. Immediately after
migrations every count is `0`. If this fails, the problem is `DATABASE_URL` or the
PostgreSQL server, and nothing further will work.

### Step 2 — run the pipeline

```shell
python run_pipeline.py run
```

This calls the live OpenWeather API, so it needs network access and a valid key.
Expected: a success line with a run ID such as `20260909T120000Z`. A run over the
default city list takes well under a minute.

### Step 3 — confirm the run was recorded

```shell
python run_pipeline.py runs
```

Expected: the run you just made, with status `succeeded` and non-zero
`city_count`, `raw_response_count` and `gold_row_count`.

Re-run `python run_pipeline.py db` and the table counts are no longer zero.

### Step 4 — start the dashboard

```shell
PYTHONPATH=src streamlit run src/dashboard/app.py
```

`PYTHONPATH=src` is required: Streamlit puts the script's own directory on the
import path, not `src`, so without it `import dashboard.db` fails.

Streamlit opens http://localhost:8501 automatically.

### Step 5 — what the audience should see

- **Landing page** — project title, a short description, and an "About this
  project" section. Navigation to the individual views is in the left sidebar.
- **Summary** — one card per active city, showing the AQI value with its label
  (Good through Very Poor), how long ago the reading was taken, and an expandable
  list of pollutant values. Readings older than three hours carry a "stale data"
  badge instead of a timestamp. A dropdown re-sorts the cards by city, by AQI, or
  by recency.
- **Compare** — pick several cities, a pollutant and a lookback window; the page
  draws a line chart over time plus a table of the latest reading per city.

If a page shows "No air pollution data available", the query worked and the table
is empty — go back to step 2. Configuration and database errors appear as a
message on the page rather than a stack trace, so read the message: it names which
of the two failed.

### Optional — replay a run without calling the API

```shell
python run_pipeline.py replay --run-id <run id from step 3>
```

Re-runs transform and load from the raw responses already stored in PostgreSQL.
Useful for demonstrating the pipeline offline, or after changing transform logic.

---

## 6. Scheduled runs

`.github/workflows/scheduler.yml` runs the pipeline daily at 12:00 UTC and can also
be triggered manually from the Actions tab. It executes
`python src/pipeline/scheduler.py` with `OPENWEATHER_API_KEY` and `DATABASE_URL`
taken from repository secrets, and returns a non-zero exit code on failure so the
workflow shows red.

The same entrypoint runs locally:

```shell
python src/pipeline/scheduler.py
```

Details and the lookback-window rationale are in
[`setup/scheduler_workflow.md`](setup/scheduler_workflow.md).

---

## 7. Tests and quality gates

```shell
cd services/pipeline
python -m pytest tests            # whole suite
python -m pytest tests/dashboard  # dashboard only
```

Tests that need a real database are skipped unless `TEST_DATABASE_URL` is set, so a
clean checkout passes without any database.

Two GitHub Actions workflows run on every pull request:

- **Python Quality Gates** — `compileall` plus the full test suite against a
  throwaway PostgreSQL service container. This one is blocking.
- **Lint Checks (Advisory)** — ruff and pyright. Findings appear as inline
  annotations on the diff; the workflow never fails the pull request.

---

## 8. Known gaps and out of scope

**Not built:**

- **City detail page** (AIR-35) — the third dashboard view was planned and never
  implemented. `dashboard/queries.py` already exposes `get_city_history()` for it,
  so the data layer is ready.
- **Azure Blob upload** — `PublishResult.azure_blob_path` exists and is always
  `None`. Nothing uploads anything.
- **HTTP API / React front end** — described in the original starter README, never
  built, deliberately replaced by Streamlit.

**Rough edges worth knowing about:**

- `requirements.txt` lists `prefect`, `duckdb`, `azure-storage-blob` and `plotly`.
  None of them is imported anywhere in the codebase. They can be removed.
- The pipeline has no retry or backoff around the OpenWeather calls. A city whose
  geocoding fails is logged and skipped; the run still reports success.
- A run in which extract returns nothing at all is still recorded as `succeeded`.
  There is no "degraded" status.
- Parquet output is best-effort by design: a write failure is recorded in the
  result and logged, and does not fail the run. PostgreSQL is the source of truth.
- The dashboard's "stale" threshold is three hours, hard-coded in
  `dashboard/format_data.py`. The scheduler runs daily, so under the scheduled
  cadence every reading looks stale between runs. Either the schedule or the
  threshold should change; the team never settled which.

---

## Where to look next

| Topic | Document |
| --- | --- |
| System structure and data flow | [`architecture/architecture.md`](architecture/architecture.md), [`architecture/data_flow_diagram.md`](architecture/data_flow_diagram.md) |
| Database schema and write boundaries | [`architecture/postgresql_schema_design.md`](architecture/postgresql_schema_design.md), [`architecture/upsert_rules.md`](architecture/upsert_rules.md) |
| Column-by-column meaning of the gold table | [`reference/data_dictionary.md`](reference/data_dictionary.md) |
| Applying, rolling back and writing migrations | [`setup/database_migrations.md`](setup/database_migrations.md) |
| Environment variables and profiles | [`setup/environment_profiles_guide.md`](setup/environment_profiles_guide.md) |
| Scheduled runs | [`setup/scheduler_workflow.md`](setup/scheduler_workflow.md) |
| Linting and type checking | [`setup/linting_and_type_checking_guide.md`](setup/linting_and_type_checking_guide.md) |
| Transform rules and contracts | [`architecture/normalization_rules.md`](architecture/normalization_rules.md), [`architecture/transform-input-output-contract.md`](architecture/transform-input-output-contract.md) |
| How the team worked | [`collaboration/team_working_agreement.md`](collaboration/team_working_agreement.md) |
