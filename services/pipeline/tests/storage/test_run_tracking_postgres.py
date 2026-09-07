"""Integration tests for PostgresPipelineRunRepository against a real test database.

Mirrors the constraint/validation coverage tests/test_run_tracking.py has for
InMemoryPipelineRunRepository, so both backends are held to the same contract.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pipeline.common import config
from pipeline.run_tracking import PipelineRunStatusUpdate, PostgresPipelineRunRepository
from pydantic import SecretStr

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 1, 2, tzinfo=timezone.utc)


@pytest.fixture
def repo(monkeypatch: pytest.MonkeyPatch, db_connection, migrated_schema):
    """Point Settings at the real test database before constructing the repository.

    `db_connection` is depended on for schema/truncation; `PostgresPipelineRunRepository` opens
    its own connections via `pipeline.common.db.get_connection()`, which reads `settings.database_url`
    directly — so that must be pointed at the test DSN (`migrated_schema`), not left as whatever
    real DATABASE_URL a developer's local .env configures.
    """
    monkeypatch.setattr(config.settings, "database_url", SecretStr(migrated_schema))
    return PostgresPipelineRunRepository()


def test_create_and_get_round_trip(repo):
    pipeline_run_id = repo.create(
        run_id="run-a", source="test", history_hours=24, window_start_utc=START, window_end_utc=END
    )

    record = repo.get("run-a")

    assert record is not None
    assert record.pipeline_run_id == pipeline_run_id
    assert record.status == "running"


def test_get_missing_run_returns_none(repo):
    assert repo.get("does-not-exist") is None


def test_create_duplicate_run_id_raises_value_error(repo):
    repo.create(run_id="run-b", source="test", history_hours=24, window_start_utc=START, window_end_utc=END)

    with pytest.raises(ValueError, match="already exists"):
        repo.create(run_id="run-b", source="test", history_hours=24, window_start_utc=START, window_end_utc=END)


def test_update_status_missing_run_raises_key_error(repo):
    with pytest.raises(KeyError):
        repo.update_status("does-not-exist", PipelineRunStatusUpdate(status="succeeded"))


def test_update_status_from_terminal_state_raises_value_error(repo):
    repo.create(run_id="run-c", source="test", history_hours=24, window_start_utc=START, window_end_utc=END)
    repo.update_status("run-c", PipelineRunStatusUpdate(status="succeeded"))

    with pytest.raises(ValueError, match="terminal status"):
        repo.update_status("run-c", PipelineRunStatusUpdate(status="failed"))


def test_update_status_applies_counters_and_finished_at(repo):
    repo.create(run_id="run-d", source="test", history_hours=24, window_start_utc=START, window_end_utc=END)

    repo.update_status(
        "run-d",
        PipelineRunStatusUpdate(status="succeeded", city_count=3, raw_response_count=3, gold_row_count=10),
    )

    record = repo.get("run-d")
    assert record.status == "succeeded"
    assert record.city_count == 3
    assert record.raw_response_count == 3
    assert record.gold_row_count == 10
    assert record.finished_at is not None


def test_update_status_rejects_negative_counters(repo):
    repo.create(run_id="run-e", source="test", history_hours=24, window_start_utc=START, window_end_utc=END)

    with pytest.raises(ValueError, match="city_count"):
        repo.update_status("run-e", PipelineRunStatusUpdate(status="succeeded", city_count=-1))


def test_list_orders_most_recent_first(repo):
    repo.create(run_id="run-f", source="test", history_hours=24, window_start_utc=START, window_end_utc=END)
    repo.create(run_id="run-g", source="test", history_hours=24, window_start_utc=START, window_end_utc=END)

    run_ids = [r.run_id for r in repo.list(limit=10)]

    assert run_ids.index("run-g") < run_ids.index("run-f")
