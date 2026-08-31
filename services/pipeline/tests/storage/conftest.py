import os
import psycopg
import pytest

from sqlalchemy.engine import make_url
from dotenv import load_dotenv
load_dotenv(dotenv_path="services/pipeline/.env")


@pytest.fixture(scope="session")
def setup_test_database():
    """Resolve Postgres URL and skip suite if unavailable."""
    raw_url = os.getenv("TEST_DATABASE_URL")
    if not raw_url :
        pytest.skip("Postgres URL not set")

    url = make_url(raw_url)
    database_name = url.database
    if not database_name.endswith("_test"):
        raise RuntimeError(
            f"Unsafe TEST_DATABASE_URL detected: /{database_name}\n"
            "Storage tests require a database name ending with '_test'."
        )

    url = raw_url.replace("postgresql+psycopg://", "postgresql://", 1)

    try:
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
    except Exception:
        pytest.skip("Postgres unreachable")

    return url
