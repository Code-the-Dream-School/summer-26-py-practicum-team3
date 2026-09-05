# Scheduler Workflow

## Entrypoint

The scheduler calls:

```bash
    python src/pipeline/scheduler.py
```

This wraps `pipeline.orchestration.run_pipeline_job(source="scheduler")` - the same
shared job used by any other entrypoint (e.g. a future manual CLI). It does not
duplicate extract/transform/load wiring; `scheduler.py` only sets the trigger source
and translates success/failure into a process exit code (0 / 1) for the scheduler
to detect.

## Working directory

`scheduler.py` must be run with the working directory set to `services/pipeline/`.
Both `.env` (via `pydantic-settings`) and `config/cities.json` (via
`settings.cities_file`) resolve as relative paths against the process's current
working directory, not against the script's location. Running from any other
directory silently loads no `.env` values and an empty cities list - there's no
error, just an empty/near-empty run (this is a known footgun; be deliberate about
`working-directory:` when wiring this into GitHub Actions).

## Schedule configuration

- **Where it lives:** `.github/workflows/scheduler.yml`, the `on.schedule.cron` field.
- **Current frequency:** `0 12 * * *` (daily at 12:00 UTC / 2:00 ET / 5:00 PT ).
- **Manual/automated-style trigger:** the workflow also listens on `workflow_dispatch`,
  so it can be run on demand from the Actions tab without waiting for the cron -
  this is what we use for verification (see below).

```yaml
on:
  schedule:
    - cron: '0 12 * * *'
  workflow_dispatch: {}
jobs:
  run:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: services/pipeline
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
        working-directory: .
      - run: python src/pipeline/scheduler.py
        env:
          OPENWEATHER_API_KEY: ${{ secrets.OPENWEATHER_API_KEY }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

## History / lookback window

- Controlled by the `HISTORY_HOURS` environment variable 
- Default `24` hours
- Loaded via `pipeline.common.config.Settings`

The scheduler entrypoint does not override this value. 
Every scheduled run uses whatever `HISTORY_HOURS` is set to in:
- `.env` (local)
- GitHub Actions secrets 

To change the lookback window for scheduled runs, update:

```
env:
  HISTORY_HOURS: 48
```

See `docs/setup/environment_profiles_guide.md` for environment profile details.


## Required environment for scheduled runs

### **GitHub Actions Secrets** 
Set in GitHub Actions → Settings → Secrets and variables → Actions 
Required:
- `OPENWEATHER_API_KEY` 
- `DATABASE_URL`

### **Workflow environment variables** (not secret): 
Set in the workflow’s env: block if overriding defaults:
- `HISTORY_HOURS`, 
- `CITIES_SOURCE`, 
- `CITIES_FILE`

These variables and their expected values are described in detail in `docs/setup/environment_profiles_guide.md`


## Manually triggering a scheduled-style run (for testing)

### - **Locally:** 
from `services/pipeline/`, run  directly:

```bash
  python src/pipeline/scheduler.py`
```

### **Via GitHub Actions:** 
1. Go to **Actions** tab 
2. Select **Scheduled Pipeline Run** workflow 
3. Click **Run workflow** 

This uses `workflow_dispatch`, exercising the same entrypoint the  cron uses.


## Verification checklist 

1. **Status:** After triggering, confirm the run exits 0 (locally) or shows a  green check (Actions). 
    A non-zero exit / red X means `scheduler.py` returned exit code 1 - check logs for the failure.
2. **Logs:** Open the job's log output and confirm structured log lines appear in order: 
   1. `Scheduler entrypoint invoked` 
   2. `Pipeline starting` 
   3. per-stage `... stage starting/complete` lines 
   4. `Pipeline succeeded` 
   5. `Scheduled pipeline run finished`.
   
   Note the `run_id` value logged.

3. **Database effect:** Using the `run_id` from step 2, query the gold table
   (`air_pollution_gold`, the default from `pipeline.load.storage.DEFAULT_TABLE_NAME`):

```sql
    SELECT * FROM air_pollution_gold WHERE run_id = '<run_id>' ORDER BY created_at DESC;
```

   Confirm rows exist*. This table is always the primary export target in `publish_outputs` -
   Postgres write is attempted on every non-empty run regardless of Parquet archival settings.

>  Note*: `pipeline_runs` status (`pipeline.run_tracking`) is currently backed by an **in‑memory** repository, not Postgres. 
   It does **not** persist across process restarts, so after a GitHub Actions job finishes, 
   it can't be queried `pipeline_runs` in the database.
>  Scheduled‑run status is verified through the workflow result (green check / red X) and the structured logs.

>  The Postgres upsert path (`save_transformed_records` → `upsert_air_quality_records`) is implemented but **inactive**.
   Once the DB connection layer is added, scheduled runs will write transformed rows to Postgres.


## Local Scheduling Using Prefect (optional enhancement)

The scheduler entrypoint (`src/pipeline/scheduler.py`) is intentionally designed
to be callable by *any* scheduler - not only GitHub Actions. This includes
Python‑native schedulers such as **Prefect**

Prefect only requires a callable that triggers the pipeline.  
`scheduler.py` already does this:

- it invokes `run_pipeline_job(source="scheduler")`
- it logs structured start/end messages
- it returns exit codes Prefect can interpret
- it does not embed pipeline logic (single responsibility)

This makes it a perfect drop‑in entrypoint for Prefect flows. 
A Prefect `@flow` can wrap the entrypoint, and a Prefect deployment can apply a cron schedule. 
This provides local automated scheduling without relying on system schedulers.
