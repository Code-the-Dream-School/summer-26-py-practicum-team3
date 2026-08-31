from __future__ import annotations

import psycopg
from alembic import command
from alembic.config import Config

from pathlib import Path

ALEMBIC_INI = Path("services/pipeline/alembic.ini")

TABLES = {
    "cities",
    "pipeline_runs",
    "raw_geocoding_responses",
    "raw_air_pollution_responses",
    "air_pollution_gold",
}


def _list_tables(setup_test_database: str) -> set[str]:
    with psycopg.connect(setup_test_database) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public';
                """
            )
            return {row[0] for row in cur.fetchall()}


def test_migration_bootstrap_upgrade_downgrade_cycle(setup_test_database: str, pytestconfig) -> None:
    """upgrade-on-empty creates all 5 tables, downgrade removes them, re-upgrade recreates them."""
    raw_url = setup_test_database

    # Alembic requires psycopg driver + escaped %
    alembic_url = raw_url.replace("postgresql://", "postgresql+psycopg://", 1).replace("%", "%%")

    # Resolve paths from repo root
    root = pytestconfig.rootpath
    ini_path = root / "services" / "pipeline" / "alembic.ini"
    script_dir = root / "services" / "pipeline" / "alembic"

    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", alembic_url)
    cfg.set_main_option("script_location", str(script_dir))

    # Start from base
    command.downgrade(cfg, "base")
    assert TABLES.isdisjoint(_list_tables(raw_url))

    # Upgrade to head → all tables exist
    command.upgrade(cfg, "head")
    tables_after_upgrade = _list_tables(raw_url)
    assert TABLES.issubset(tables_after_upgrade)

    # Downgrade again → tables removed
    command.downgrade(cfg, "base")
    tables_after_downgrade = _list_tables(raw_url)
    assert TABLES.isdisjoint(tables_after_downgrade)

    # Re-upgrade → tables recreated
    command.upgrade(cfg, "head")
    tables_after_reupgrade = _list_tables(raw_url)
    assert TABLES.issubset(tables_after_reupgrade)
