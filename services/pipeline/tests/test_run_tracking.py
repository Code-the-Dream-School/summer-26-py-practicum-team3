"""Unit tests for pipeline run tracking functionality and schema constraints."""

from datetime import datetime, timezone
import time
import pytest

from pipeline.run_tracking import (
    InMemoryPipelineRunRepository,
    PipelineRunRecord,
    PipelineRunStatusUpdate,
    _default_repository,
    create_pipeline_run,
    update_pipeline_run_status,
)


@pytest.fixture(autouse=True)
def clean_default_repository():
    """Ensure module-level store is clean before and after each test."""
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


# ============================================================================
# 1. Default Factory & Unit Object Tests
# ============================================================================

def test_pipeline_run_record_default_factory(valid_timestamps):
    """Verifies default_factory creates fresh dynamic timestamps per instance."""
    start, end = valid_timestamps
    record1 = PipelineRunRecord(
        pipeline_run_id=1,
        run_id="run-1",
        source="openweather",
        history_hours=6,
        window_start_utc=start,
        window_end_utc=end,
    )
    # Ensure distinct clock ticks between object instantiations
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
    # Regression check: timestamps must differ, proving evaluation at instantiate time
    assert record1.created_at < record2.created_at


# ============================================================================
# 2. Constraint & Validation Tests
# ============================================================================

@pytest.mark.parametrize("invalid_run_id", ["", "   ", "\t\n"])
def test_create_pipeline_run_empty_run_id(repo, valid_timestamps, invalid_run_id):
    """Empty or whitespace-only run_id must raise ValueError."""
    start, end = valid_timestamps
    with pytest.raises(ValueError, match="run_id cannot be empty"):
        repo.create(invalid_run_id, "openweather", 6, start, end)


def test_create_pipeline_run_duplicate_raises_error(repo, valid_timestamps):
    """Mimics UNIQUE constraint on run_id: second insert must raise ValueError."""
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
    """End time strictly earlier than start time must be rejected."""
    start = datetime(2026, 8, 26, 6, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="must be >="):
        repo.create("run-1", "openweather", 6, start, end)


def test_create_pipeline_run_boundary_window_equal(repo):
    """Boundary check: window_end_utc == window_start_utc is valid (>= constraint)."""
    ts = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
    rec_id = repo.create("run-boundary-001", "openweather", 6, ts, ts)

    assert rec_id == 1
    record = repo.get("run-boundary-001")
    assert record is not None
    assert record.window_start_utc == record.window_end_utc == ts


def test_update_status_invalid_status_enum(repo, valid_timestamps):
    start, end = valid_timestamps
    repo.create("run-1", "openweather", 6, start, end)

    update = PipelineRunStatusUpdate(status="success")  # Typo instead of 'succeeded'
    with pytest.raises(ValueError, match="Invalid status"):
        repo.update_status("run-1", update)


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


# ============================================================================
# 3. Functional Execution & Partial Update Tests
# ============================================================================

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
    """Verifies that terminal states without explicit finished_at get populated automatically."""
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
    assert rec.city_count == 0  # Preserved from initial default
    assert rec.error_message == "Network failure"
    assert rec.finished_at is not None
    assert rec.finished_at.tzinfo == timezone.utc


def test_update_run_not_found(repo):
    update = PipelineRunStatusUpdate(status="succeeded")
    with pytest.raises(KeyError, match="not found"):
        repo.update_status("unknown-run", update)