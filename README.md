# City Air Tracker

A batch ETL pipeline and dashboard for city air quality, built by Team 3 for the
Code the Dream Python practicum.

The pipeline geocodes a configured list of cities, pulls historical air-pollution
readings from the OpenWeather API, normalizes them into a gold dataset in
PostgreSQL, and records every run. A Streamlit dashboard reads that data and shows
current conditions per city and how they change over time.

**Stack:** Python 3.12 · PostgreSQL (Alembic migrations) · psycopg 3 · pandas ·
Streamlit · GitHub Actions for scheduling and CI.

## Quick start

Requires Python 3.12+, a running PostgreSQL server, and an OpenWeather API key.

```shell
python -m venv services/pipeline/venv
source services/pipeline/venv/bin/activate
pip install -r requirements.txt

cp .env.example services/pipeline/.env      # fill in OPENWEATHER_API_KEY and DATABASE_URL
createdb city_air_tracker

cd services/pipeline
alembic upgrade head                        # create the tables
python run_pipeline.py run                  # fetch and load data
PYTHONPATH=src streamlit run src/dashboard/app.py
```

The dashboard opens at http://localhost:8501.

Note that the `.env` that is actually read lives in `services/pipeline/`, not at the
repository root — every command above is run from `services/pipeline`.

## Command-line tools

Run from `services/pipeline`:

| Command | What it does |
| --- | --- |
| `python run_pipeline.py run` | Run the pipeline end to end |
| `python run_pipeline.py runs` | Show recent run history |
| `python run_pipeline.py db` | Connection status and per-table row counts |
| `python run_pipeline.py replay --run-id <id>` | Re-run transform and load from stored raw responses, without calling the API |
| `python src/pipeline/scheduler.py` | The entrypoint used by the scheduled workflow |

## Repository layout

```
services/pipeline/
  src/pipeline/        extract, transform, load, orchestration, CLI, scheduler
  src/dashboard/       Streamlit app, pages, queries, formatting helpers
  alembic/             database migrations
  config/cities.json   the list of cities to process
  tests/               pytest suite
docs/                  architecture, setup and reference documentation
requirements.txt       dependencies for the whole project
```

## Documentation

**[`docs/handoff.md`](docs/handoff.md)** is the place to start: what was built, every
runtime setting, a step-by-step local walkthrough, and what is still unfinished.

[`docs/README.md`](docs/README.md) is the full index of the rest.

## Testing

```shell
cd services/pipeline
python -m pytest tests
```

Tests that need a real database are skipped unless `TEST_DATABASE_URL` is set.

---

<details>
<summary>Team repository setup (Sprint 0, historical)</summary>

These are the Code the Dream instructions the team followed to create this
repository. They are kept for reference and are not needed to run the project.

One student completed the setup below.

1. Sign into GitHub and create a public repository for the team's City Air Tracker
   project. Do not create a `.gitignore` or a `README.md`.
2. Clone the [`city-air-tracker-student`](https://github.com/Code-the-Dream-School/city-air-tracker-student)
   repository — not the repository you just created.
3. From the `city-air-tracker-student` directory, repoint the remotes, replacing
   `team-repository-owner` and `team-repository-name`:

```shell
# SSH authentication:
git remote set-url origin git@github.com:team-repository-owner/team-repository-name.git

# token-based authentication:
git remote set-url origin https://github.com/team-repository-owner/team-repository-name

git remote add upstream https://github.com/Code-the-Dream-School/city-air-tracker-student
git push origin main
```

4. Add every student and mentor on the team as a collaborator.
5. Everyone else clones the team repository:

```shell
git clone https://github.com/team-repository-owner/team-repository-name.git
cd team-repository-name
git remote add upstream https://github.com/Code-the-Dream-School/city-air-tracker-student
```

`git remote -v` should show `origin` pointing at the team repository and `upstream`
at the Code the Dream starter.

</details>
