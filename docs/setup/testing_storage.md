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

Tests live under: `services/pipeline/tests/`

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

## Required Environment Variables

The storage tests require a PostgreSQL connection string.  
Add the following to your `.env` or export it in your shell:

### **Local development (example)**

```env
TEST_DATABASE_URL=postgresql+psycopg://<username>:<password>@localhost:5433/city_air_tracker_test
```

Use the port that matches your local test database.

## Notes

- Some tests are intentionally marked xfail until the SQL layer is updated.

- Migration tests ensure schema consistency across fresh installs and downgrades.

- Storage tests are integration tests and require a real database, not mocks.