import psycopg
from sqlalchemy.engine import make_url

def test_database_name_is_safe(setup_test_database):
    assert isinstance(setup_test_database, str)
    assert setup_test_database.startswith("postgresql://")

    url = make_url(setup_test_database)
    database_name = url.database

    assert database_name.endswith("_test"), (
        f"Unsafe database name detected: '{database_name}'. "
        "Storage tests require a database ending with '_test'."
    )

def test_database_is_reachable(setup_test_database):
    with psycopg.connect(setup_test_database) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            assert cur.fetchone()[0] == 1
