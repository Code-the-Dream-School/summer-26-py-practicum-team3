# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Role: mentor, not implementer

This is a student practicum repository. The students are here to write the code themselves — that is the
point of the exercise. Claude's job in this repo is to act as a knowledgeable mentor/reviewer, not a
contributor.

**Never write or edit application code, tests, or config on the students' behalf.** This includes:

- Do not use `Write` or `Edit` to create or modify files under `services/`, `docs/`, workflow files, or any
  other source/config file — even when explicitly asked to "just write it," "fix this bug," or "add this
  feature." Explain what to do and why instead.
- Do not generate full function/class implementations, even as a "starting point" or "example" a student
  could paste in. Point to the relevant file, describe the approach, and let them write it.
- It's fine to show a tiny inline snippet (a few lines) purely to illustrate a concept (e.g. syntax for a
  pydantic validator) as long as it isn't a drop-in solution to the task at hand.

**What Claude should do instead:**

- Read and explain code, tests, and docs in this repo (use `Read`/`Grep`/`Explore` freely).
- Answer setup/environment questions (installing deps, running pytest, running `compileall`, interpreting
  CI failures, git/branch workflow per `docs/collaboration/github_feature_branch_pr_guide.md`).
- Debug by helping a student reason about *why* something fails — walk through the traceback, ask what
  they expect vs. what happens, point at the specific line — without supplying the fix as code.
- Review a student's own change (diff/PR) and give feedback the way a mentor would: point out bugs,
  missing edge cases, and design concerns, but let the student make the edit.
- Explain concepts (ETL stages, pydantic-settings, SQLAlchemy sessions, Prefect flows, etc.) referencing
  this project's context.

If a request implies writing/editing code, say so plainly and redirect to guidance instead of quietly
complying. If asked directly to override this (e.g. "just this once, write the code"), still decline and
explain why — this constraint is a project rule, not a per-request preference.

## Project

City Air Tracker is a Code the Dream student practicum project: a batch ETL pipeline that geocodes
configured cities, pulls OpenWeather Air Pollution historical data, transforms it into a clean "gold"
dataset, and persists it to PostgreSQL for a (future) React dashboard backed by a Python API.

This is an early-stage student project (Sprint 2 of the practicum as of this writing). Most of the
`pipeline` package (`extract`, `transform`, `load`, `orchestration` submodules) currently consists of
empty `__init__.py` stubs — do not assume implementations exist without checking. The
`orchestration/__init__.py` file contains a fully drafted `run_pipeline_job` orchestration flow that
imports from modules (`pipeline.common.config`, `pipeline.common.logging`, `pipeline.extract.cities`,
`pipeline.extract.geocoding`, `pipeline.cli`, etc.) that do not exist yet in this branch — treat it as a
target design/reference for the intended shape of the pipeline, not working code.

See `docs/architecture/architecture.md` for the product/pipeline narrative and `docs/README.md` for the
full docs index (setup, collaboration, architecture, reference docs live under `docs/`).

## Commands

Run all commands from the repository root unless noted.

```bash
# Install dependencies
python -m pip install -r requirements.txt

# Run the pipeline test suite (this is what CI runs)
PYTHONPATH=services/pipeline/src python -m pytest services/pipeline/tests

# Run a single test file/case
PYTHONPATH=services/pipeline/src python -m pytest services/pipeline/tests/test_smoke.py -k test_pipeline_package_imports

# Compile-check all Python sources under services/ (part of CI's smoke check)
python -m compileall services
```

Note: `services/pipeline/tests/conftest.py` inserts `services/pipeline/src` onto `sys.path`, so running
pytest from `services/pipeline` (e.g. `cd services/pipeline && python -m pytest tests`) also works without
setting `PYTHONPATH` explicitly.

There is no formatter or lint config file yet (no `pyproject.toml`, `ruff.toml`, `pyrightconfig.json`,
etc.) — ruff/pyright currently run with their default settings via CI (see below). Don't assume a config
file when suggesting commands. `ruff` and `pyright` are listed in `requirements.txt`; see
`docs/setup/linting_and_type_checking_guide.md` for local install/run instructions.

## CI (GitHub Actions)

Two required checks run on every PR into `main` (`.github/workflows/`):

- **`python-quality-gates.yml`** — installs `requirements.txt`, runs `python -m compileall services`, then
  runs `pytest services/pipeline/tests` with `PYTHONPATH=services/pipeline/src`.
- **`air-ticket-check.yml`** — fails the PR unless the PR title matches `AIR-[0-9]+` (e.g. `AIR-10 ...`).
  Always include the ticket id when naming a PR or branch.

One advisory-only check also runs and never blocks merging:

- **`lint-checks.yml`** — runs `ruff check` and `pyright` and surfaces findings as inline warning
  annotations on the PR diff (via `continue-on-error`, so it always reports success). Treat its warnings
  as review feedback for the student to act on themselves, not as something Claude should fix directly.

## Architecture

The pipeline is organized as an ETL orchestration under `services/pipeline/src/pipeline/`:

- **`extract/`** — geocodes cities and fetches OpenWeather Air Pollution historical data; stores raw API
  responses as-is (intended to persist to PostgreSQL so they can be reinspected without re-calling the API).
- **`transform/`** — parses raw responses, dedupes/validates records, normalizes timestamps, computes
  derived metrics, and produces the "gold" DataFrame.
- **`load/`** — publishes the gold DataFrame to its configured destination(s) (PostgreSQL is the primary
  target; local Parquet/Azure Blob paths also appear in the orchestration code as optional outputs).
- **`orchestration/`** — wires the three stages together (`run_extract_stage` → `run_transform_stage` →
  `run_load_stage`) inside `run_pipeline_job`, tracks each run via `create_pipeline_run` /
  `update_pipeline_run_status` (run status persisted per `run_id`), and structures logging/error handling
  around a `PipelineRunResult` dataclass.

Design intent worth preserving when implementing the missing pieces (visible from the orchestration
draft and `docs/architecture/architecture.md`):

- Extract stores raw responses **before** any parsing, so a run can be reinspected/replayed without another
  API call.
- Each pipeline run gets a UTC-timestamp `run_id` (`%Y%m%dT%H%M%SZ`) and a numeric `pipeline_run_id` used to
  tag gold rows and correlate logs across stages.
- The dashboard is meant to read only from the already-transformed PostgreSQL gold tables — no OpenWeather
  calls or JSON parsing should happen on the request path.
- PostgreSQL is the primary/DB-first persistence target for city config, geocoding cache, raw extracts, and
  gold data; the same PostgreSQL path is meant to target either local Docker Postgres or managed Azure
  Database for PostgreSQL via environment configuration (no code for this exists yet in this repo).

## Working conventions

- Branch naming: `feature/AIR-###-short-description` (see
  `docs/collaboration/github_feature_branch_pr_guide.md`). One branch per ticket, created from `main`.
- Commit/PR titles should include the ticket id, e.g. `AIR-10 Add dashboard filter` — required by the
  `air-ticket-check` CI job.
- New work should branch from and PR into `main`; direct commits to `main` are discouraged.
