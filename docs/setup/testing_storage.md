# Storage Layer Testing

This document describes how to test the City Air Tracker storage layer, including raw loaders, transformed record loaders, upsert behavior, and migration/bootstrap workflows. These tests ensure that the database schema created by Alembic supports all persistence operations used by the pipeline.

---

## Overview

The storage tests validate:

- writing raw geocoding and raw air‑pollution responses  
- writing transformed (gold) analytical records  
- upsert behavior (no duplicates, updates existing rows)  
- handling empty or missing input  
- applying migrations to an empty database

## Test Coverage
1. Writing new raw and transformed records  
  - Verifies that inserts into raw and gold tables succeed and produce exactly one row.

2. Upsert behavior (no duplicates)
-1. **Writing new raw and transformed records**  
   - Verifies that inserts into raw and gold tables succeed and produce exactly one row.

2. **Upsert behavior (no duplicates)**  
   - Re-running the same transformed input should not create duplicates.

3. **Updating existing records**  
   - Ensures upsert updates an existing gold record instead of inserting a new one.

4. **Empty or missing input**  
   Confirms:
   - empty transformed datasets are skipped  
   - missing required fields raise errors  
   - loaders do not write invalid rows  

5. **Migration/bootstrap workflow**  
   Validates that:
   - `alembic upgrade head` creates all tables on an empty DB  
   - `alembic downgrade base` removes them  
   - re‑upgrade recreates them cleanly  

## Running Tests Locally
Use your local test database. Make sure PostgreSQL is running locally. Add the database connection string to your `.env` file

Ran locally from root against a real PostgreSQL instance:

```bash
pytest -v -s services/pipeline/tests/storage
```

You can also run the tests from the pipeline directory:

```bash
cd services/pipeline
pytest tests/storage
```

The storage tests use a real PostgreSQL database. The test database is created automatically if it does not already exist.

## Required Environment Variables

The storage tests require a PostgreSQL connection string. The `.env` used by the pipeline and Alembic file is located at:  `services/pipeline/.env`  

### **Local development (example)**

```env
TEST_DATABASE_URL=postgresql+psycopg://<username>:<password>@localhost:5433/city_air_tracker_test
```

Use the port that matches your local test database.


## Environment Loading Flow 

Tests → `load_dotenv(dotenv_path="services/pipeline/.env")` → loads `services/pipeline/.env`

Alembic → `load_dotenv()` → checks `services/pipeline/.env` → if missing → falls back to `services/.env`


## Troubleshooting

1. `.env` location 

The pipeline's `.env` file is intentionally located under: `services/pipeline/.env` because both Alembic and the storage test suite operate from the **pipeline directory**, not the project root.
Alembic configuration, its migrations, and `env.py` are part of the pipeline service and are run from `services/pipeline`.
Alembic is run from the pipeline directory:

```bash
cd services/pipeline
alembic upgrade head
```

`alembic/env.py` uses `load_dotenv()`, so keeping the `.env` with the `pipeline/Alembic` setup ensures the database environment variables are available when migrations are executed.

The storage test suite (`tests/storage/conftest.py`) uses the same environment configuration to obtain `TEST_DATABASE_URL`, create the test database when needed, and run the Alembic migrations before the executing storage tests.


2. `pytest.ini` 

An empty `pytest.ini` is intentionally kept at the repository root. 

This allows pytest to discover the repository root as its `rootdir` even when tests are started from the pipeline directory:

```bash
cd services/pipeline
pytest tests
```

This keeps the test command consistent while allowing the pipeline `.env` and Alembic configuration to remain under `services/pipeline`.

3. If the storage tests are skipped with `Postgres URL not set`, verify that:

- `services/pipeline/.env` exists.
- `TEST_DATABASE_URL` is defined.
- PostgreSQL is running on your machine.
- The database URL uses the correct host and port.
- The database name ends with `_test`. (If the database does not exist, the test suite will create it.)
- Add `pytest.ini` at the repository root if it does not exist, so pytest resolves the correct rootdir and loads the pipeline `.env`.


## Notes

- Migration tests ensure schema consistency across fresh installs and downgrades.

- Storage tests are integration tests and require a real database, not mocks.
