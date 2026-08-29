"""Pipeline run tracking module providing status and metrics persistence.

Implements the contract required by orchestration and mirrors the schema and
CHECK constraints defined in docs/architecture/postgresql_schema_design.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from pipeline.common.logging import get_logger

log = get_logger(__name__)

VALID_STATUSES = {"running", "succeeded", "failed"}
TERMINAL_STATUSES = {"succeeded", "failed"}


@dataclass
class PipelineRunStatusUpdate:
    """Container for pipeline run update fields."""

    status: str
    city_count: int | None = None
    raw_response_count: int | None = None
    gold_row_count: int | None = None
    error_message: str | None = None
    finished_at: datetime | None = None


@dataclass
class PipelineRunRecord:
    """In-memory representation of a pipeline_runs table row."""

    pipeline_run_id: int
    run_id: str
    source: str
    history_hours: int
    window_start_utc: datetime
    window_end_utc: datetime
    status: str = "running"
    city_count: int = 0
    raw_response_count: int = 0
    gold_row_count: int = 0
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None


class InMemoryPipelineRunRepository:
    """In-memory repository implementing DB schema constraints."""

    def __init__(self) -> None:
        self._runs_store: dict[str, PipelineRunRecord] = {}
        self._next_id: int = 1

    def clear(self) -> None:
        """Reset repository state (useful for tests)."""
        self._runs_store.clear()
        self._next_id = 1

    def create(
        self,
        run_id: str,
        source: str,
        history_hours: int,
        window_start_utc: datetime,
        window_end_utc: datetime,
    ) -> int:
        """Creates a new pipeline run record enforcing schema constraints."""
        if not run_id or not run_id.strip():
            raise ValueError("run_id cannot be empty.")

        if window_start_utc.tzinfo is None or window_end_utc.tzinfo is None:
            raise ValueError("window_start_utc and window_end_utc must be timezone-aware (UTC).")

        if history_hours <= 0:
            raise ValueError(f"history_hours must be > 0, got {history_hours}.")

        if window_end_utc < window_start_utc:
            raise ValueError(
                f"window_end_utc ({window_end_utc}) must be >= window_start_utc ({window_start_utc})."
            )

        if run_id in self._runs_store:
            log.error("Failed to create pipeline run: run_id already exists", extra={"run_id": run_id})
            raise ValueError(f"Pipeline run with run_id='{run_id}' already exists.")

        record_id = self._next_id
        self._next_id += 1

        record = PipelineRunRecord(
            pipeline_run_id=record_id,
            run_id=run_id,
            source=source,
            history_hours=history_hours,
            window_start_utc=window_start_utc,
            window_end_utc=window_end_utc,
            status="running",
            city_count=0,
            raw_response_count=0,
            gold_row_count=0,
        )

        self._runs_store[run_id] = record

        log.info(
            "Pipeline run record created",
            extra={
                "run_id": run_id,
                "pipeline_run_id": record_id,
                "status": "running",
                "source": source,
            },
        )
        return record_id

    def update_status(self, run_id: str, update: PipelineRunStatusUpdate) -> None:
        """Updates pipeline run status with CHECK constraints, state machine guards, and partial updates."""
        if update.status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{update.status}'. Must be one of: {VALID_STATUSES}"
            )

        record = self._runs_store.get(run_id)
        if not record:
            log.error("Failed to update status: run_id not found", extra={"run_id": run_id})
            raise KeyError(f"Pipeline run '{run_id}' not found.")

        if record.status in TERMINAL_STATUSES:
            raise ValueError(
                f"Cannot transition run '{run_id}' from terminal status '{record.status}' to '{update.status}'."
            )

        for name, val in [
            ("city_count", update.city_count),
            ("raw_response_count", update.raw_response_count),
            ("gold_row_count", update.gold_row_count),
        ]:
            if val is not None and val < 0:
                raise ValueError(f"{name} must be >= 0, got {val}")

        record.status = update.status

        if update.city_count is not None:
            record.city_count = update.city_count
        if update.raw_response_count is not None:
            record.raw_response_count = update.raw_response_count
        if update.gold_row_count is not None:
            record.gold_row_count = update.gold_row_count
        if update.error_message is not None:
            record.error_message = update.error_message

        # Explicit finished_at takes precedence; fallback to now() if transitioning to terminal state
        if update.finished_at is not None:
            record.finished_at = update.finished_at
        elif update.status in TERMINAL_STATUSES and record.finished_at is None:
            record.finished_at = datetime.now(timezone.utc)

        log.info(
            "Pipeline run status updated",
            extra={
                "run_id": run_id,
                "pipeline_run_id": record.pipeline_run_id,
                "status": record.status,
                "city_count": record.city_count,
                "raw_response_count": record.raw_response_count,
                "gold_row_count": record.gold_row_count,
            },
        )

    def get(self, run_id: str) -> PipelineRunRecord | None:
        """Retrieve a run record by run_id."""
        return self._runs_store.get(run_id)


# Default module-level repository instance
_default_repository = InMemoryPipelineRunRepository()


def create_pipeline_run(
    run_id: str,
    source: str,
    history_hours: int,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> int:
    """Creates a new pipeline run record."""
    return _default_repository.create(
        run_id=run_id,
        source=source,
        history_hours=history_hours,
        window_start_utc=window_start_utc,
        window_end_utc=window_end_utc,
    )


def update_pipeline_run_status(run_id: str, update: PipelineRunStatusUpdate) -> None:
    """Updates the status and counters of an existing pipeline run."""
    _default_repository.update_status(run_id=run_id, update=update)