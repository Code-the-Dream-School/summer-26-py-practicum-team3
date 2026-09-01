import psycopg


def test_migration_creates_tables(setup_test_database, migrated_schema):
    with psycopg.connect(setup_test_database) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public';
            """)
            tables = {row[0] for row in cur.fetchall()}

    expected = {
        "cities",
        "pipeline_runs",
        "raw_geocoding_responses",
        "raw_air_pollution_responses",
        "air_pollution_gold",
        "alembic_version",
    }

    assert expected.issubset(tables)


def test_cities_columns(migrated_schema, setup_test_database):
    with psycopg.connect(setup_test_database) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'cities';
            """)
            cols = {row[0] for row in cur.fetchall()}

    assert "city_id" in cols
    assert "city_name" in cols
    assert "country_code" in cols


def test_raw_geocoding_fk(migrated_schema, setup_test_database):
    with psycopg.connect(setup_test_database) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'raw_geocoding_responses'
                AND constraint_type = 'FOREIGN KEY';
            """)
            fks = {row[0] for row in cur.fetchall()}

    assert "raw_geocoding_pipeline_run_fk" in fks
    assert "raw_geocoding_city_fk" in fks


def test_indexes_exist(migrated_schema, setup_test_database):
    with psycopg.connect(setup_test_database) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public';
            """)
            idx = {row[0] for row in cur.fetchall()}

    assert "cities_city_identity_unique" in idx
    assert "idx_raw_geocoding_pipeline_run" in idx
    assert "idx_raw_air_pollution_pipeline_run" in idx

