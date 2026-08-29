# Database Migrations

The City Air Tracker database schema is managed with Alembic migrations.

## Prerequisites

Install the project dependencies:

```bash
cd services/pipeline
pip install -r requirements.txt
```
Make sure PostgreSQL is running locally.

Add the database connection string to your .env file:

### `.env.example`

Make sure it includes:

```env
DATABASE_URL=postgresql+psycopg://<username>:<password>@localhost:5432/city_air_tracker
```

## Apply the Database Schema

Alembic is configured under services/pipeline/. Run the migration commands from that directory:

```
cd services/pipeline
```

To create the database schema:

```
alembic upgrade head
```

The initial migration creates:

cities
pipeline_runs
raw_geocoding_responses
raw_air_pollution_responses
air_pollution_gold

The tables are created in dependency order so the foreign-key relationships can be created successfully.

## Roll Back a Migration

To roll back the initial schema:

```
alembic downgrade base
```

To roll back one migration:

```
alembic downgrade -1
```

## Creating a New Migration

When the database schema needs to change, create a new migration from services/pipeline/:

```
alembic revision -m "describe the schema change"
```

Update the generated migration with the required changes in both upgrade() and downgrade().

For example:

def upgrade():
    # Add the schema change here.
    pass


def downgrade():
    # Reverse the schema change here.
    pass

Apply the new migration with:

alembic upgrade head

## Migration Workflow

When making a schema change:

1. Update the database schema documentation if needed.
2. Create a new Alembic migration.
3. Implement both upgrade() and downgrade().
4. Run the migration against a local PostgreSQL database.
5. Verify the schema changes.
6. Test the downgrade.
7. Commit the migration with the related code changes.

Do not manually modify tables in a shared database instead of creating a migration.

## Verify a Migration

Before opening a PR, test the migration against a scratch PostgreSQL database.

From services/pipeline/:

```
alembic upgrade head
```

Verify that the expected tables, constraints, and indexes were created.

Then test the rollback:

```
alembic downgrade base
```

Verify that the schema was removed successfully.

Finally, run:

```
alembic upgrade head
```

This confirms that the schema can be created from an empty database and successfully recreated after a rollback.

## Troubleshooting
1. DATABASE_URL is missing

Make sure .env contains:

```
DATABASE_URL=postgresql+psycopg://<username>:<password>@localhost:5432/city_air_tracker
```

2. Alembic cannot find alembic.ini

Make sure you are running the commands from:

```
cd services/pipeline
```

Then run:

```
alembic upgrade head
```

## Check the current migration

To see the migration currently applied:

```
alembic current
```

To see the migration history:

```
alembic history
```

Also add this to `.env`:

```env
DATABASE_URL=postgresql+psycopg://<username>:<password>@localhost:5432/city_air_tracker
```