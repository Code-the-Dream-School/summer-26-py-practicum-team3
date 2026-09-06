"""Unit tests for pipeline run tracking functionality and schema constraints."""

from datetime import datetime, timezone
import time
import pytest
from pydantic import SecretStr

from pipeline.common import config
from pipeline.run_tracking import (
    InMemoryPipelineRunRepository,
    PipelineRunRecord,
    PipelineRunStatusUpdate,
    _default_repository,
    create_pipeline_run,
    update_pipeline_run_status,
)


@pytest.fixture(autouse=True)
def clean_default_repository(monkeypatch: pytest.MonkeyPatch):
    """Ensure module-level store is clean before and after each test.

    Also forces DATABASE_URL empty for the duration of this suite: these tests exercise
    InMemoryPipelineRunRepository in isolation and must not silently switch to a real Postgres
    connection just because a developer's local .env happens to configure one.
    """
    monkeypatch.setattr(config.settings, "database_url", SecretStr(""))
    _default_repository.clear()
    yield
    _default_repository.clear()


@pytest.fixture
def repo():
    """Fixture providing an isolated repository instance for direct tests."""
    return InMemoryPipelineRunRepository()


@pytest.fixture
def valid_timestamps():
    start = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 26, 6, 0, tzinfo=timezone.utc)
    return start, end


def test_pipeline_run_record_default_factory(valid_timestamps):
    start, end = valid_timestamps
    record1 = PipelineRunRecord(
        pipeline_run_id=1,
        run_id="run-1",
        source="openweather",
        history_hours=6,
        window_start_utc=start,
        window_end_utc=end,
    )
    time.sleep(0.001)
    record2 = PipelineRunRecord(
        pipeline_run_id=2,
        run_id="run-2",
        source="openweather",
        history_hours=6,
        window_start_utc=start,
        window_end_utc=end,
    )

    assert record1.created_at.tzinfo == timezone.utc
    assert record2.created_at.tzinfo == timezone.utc
    assert record1.created_at < record2.created_at


@pytest.mark.parametrize("invalid_run_id", ["", "   ", "\t\n"])
def test_create_pipeline_run_empty_run_id(repo, valid_timestamps, invalid_run_id):
    start, end = valid_timestamps
    with pytest.raises(ValueError, match="run_id cannot be empty"):
        repo.create(invalid_run_id, "openweather", 6, start, end)


def test_create_pipeline_run_naive_datetimes_raise_error(repo):
    naive_start = datetime(2026, 8, 26, 0, 0)
    naive_end = datetime(2026, 8, 26, 6, 0)
    with pytest.raises(ValueError, match="timezone-aware"):
        repo.create("run-naive", "openweather", 6, naive_start, naive_end)


def test_create_pipeline_run_duplicate_raises_error(repo, valid_timestamps):
    start, end = valid_timestamps
    run_id = "run-duplicate-001"
    repo.create(run_id, "openweather", 6, start, end)

    with pytest.raises(ValueError, match="already exists"):
        repo.create(run_id, "openweather", 6, start, end)


def test_create_pipeline_run_invalid_history_hours(repo, valid_timestamps):
    start, end = valid_timestamps
    with pytest.raises(ValueError, match="history_hours must be > 0"):
        repo.create("run-1", "openweather", 0, start, end)


def test_create_pipeline_run_invalid_window(repo):
    start = datetime(2026, 8, 26, 6, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="must be >="):
        repo.create("run-1", "openweather", 6, start, end)


def test_create_pipeline_run_boundary_window_equal(repo):
    ts = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
    rec_id = repo.create("run-boundary-001", "openweather", 6, ts, ts)

    assert rec_id == 1
    record = repo.get("run-boundary-001")
    assert record is not None
    assert record.window_start_utc == record.window_end_utc == ts


def test_update_status_invalid_status_enum(repo, valid_timestamps):
    start, end = valid_timestamps
    repo.create("run-1", "openweather", 6, start, end)

    update = PipelineRunStatusUpdate(status="success")
    with pytest.raises(ValueError, match="Invalid status"):
        repo.update_status("run-1", update)


def test_update_status_from_terminal_status_raises_error(repo, valid_timestamps):
    start, end = valid_timestamps
    repo.create("run-term-001", "openweather", 6, start, end)
    repo.update_status("run-term-001", PipelineRunStatusUpdate(status="succeeded"))

    with pytest.raises(ValueError, match="Cannot transition run .* from terminal status"):
        repo.update_status("run-term-001", PipelineRunStatusUpdate(status="running"))

    with pytest.raises(ValueError, match="Cannot transition run .* from terminal status"):
        repo.update_status("run-term-001", PipelineRunStatusUpdate(status="failed"))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"city_count": -1},
        {"raw_response_count": -5},
        {"gold_row_count": -10},
    ],
)
def test_update_status_negative_counters(repo, valid_timestamps, kwargs):
    start, end = valid_timestamps
    repo.create("run-1", "openweather", 6, start, end)

    update = PipelineRunStatusUpdate(status="succeeded", **kwargs)
    with pytest.raises(ValueError, match="must be >= 0"):
        repo.update_status("run-1", update)


def test_create_and_update_success_via_module_functions(valid_timestamps):
    start, end = valid_timestamps
    run_id = "run-2026-08-26-001"

    rec_id = create_pipeline_run(
        run_id=run_id,
        source="openweather",
        history_hours=6,
        window_start_utc=start,
        window_end_utc=end,
    )

    assert rec_id == 1
    finished_at = datetime(2026, 8, 26, 6, 5, tzinfo=timezone.utc)
    update = PipelineRunStatusUpdate(
        status="succeeded",
        city_count=5,
        raw_response_count=5,
        gold_row_count=120,
        finished_at=finished_at,
    )
    update_pipeline_run_status(run_id, update)

    rec = _default_repository.get(run_id)
    assert rec is not None
    assert rec.pipeline_run_id == 1
    assert rec.status == "succeeded"
    assert rec.city_count == 5
    assert rec.raw_response_count == 5
    assert rec.gold_row_count == 120
    assert rec.finished_at == finished_at


def test_update_failed_auto_populates_finished_at(repo, valid_timestamps):
    start, end = valid_timestamps
    run_id = "run-fail-001"
    repo.create(run_id, "openweather", 6, start, end)

    update = PipelineRunStatusUpdate(
        status="failed",
        city_count=None,
        error_message="Network failure",
        finished_at=None,
    )
    repo.update_status(run_id, update)

    rec = repo.get(run_id)
    assert rec is not None
    assert rec.status == "failed"
    assert rec.city_count == 0
    assert rec.error_message == "Network failure"
    assert rec.finished_at is not None
    assert rec.finished_at.tzinfo == timezone.utc


def test_update_run_not_found(repo):
    update = PipelineRunStatusUpdate(status="succeeded")
    with pytest.raises(KeyError, match="not found"):
        repo.update_status("unknown-run", update)