"""Pipeline run tracking module providing status and metrics persistence.

Implements the contract required by orchestration and mirrors the schema and
CHECK constraints defined in docs/architecture/postgresql_schema_design.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import psycopg

from pipeline.common.config import settings
from pipeline.common.db import get_connection
from pipeline.common.logging import get_logger

log = get_logger(__name__)

VALID_STATUSES = {"running", "succeeded", "failed"}
TERMINAL_STATUSES = {"succeeded", "failed"}

_SELECT_COLUMNS = (
    "pipeline_run_id",
    "run_id",
    "source",
    "history_hours",
    "window_start_utc",
    "window_end_utc",
    "status",
    "city_count",
    "raw_response_count",
    "gold_row_count",
    "error_message",
    "created_at",
    "finished_at",
)
_SELECT_SQL = f"SELECT {', '.join(_SELECT_COLUMNS)} FROM pipeline_runs"  # noqa: S608


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


def _row_to_record(row: tuple) -> PipelineRunRecord:
    (
        pipeline_run_id,
        run_id,
        source,
        history_hours,
        window_start_utc,
        window_end_utc,
        status,
        city_count,
        raw_response_count,
        gold_row_count,
        error_message,
        created_at,
        finished_at,
    ) = row
    return PipelineRunRecord(
        pipeline_run_id=pipeline_run_id,
        run_id=run_id,
        source=source,
        history_hours=history_hours,
        window_start_utc=window_start_utc,
        window_end_utc=window_end_utc,
        status=status,
        city_count=city_count,
        raw_response_count=raw_response_count,
        gold_row_count=gold_row_count,
        error_message=error_message,
        created_at=created_at,
        finished_at=finished_at,
    )


def _validate_create_args(
    run_id: str,
    history_hours: int,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> None:
    """Shared schema-constraint validation for creating a pipeline run."""
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


def _validate_status_value(status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}")


def _validate_counters(update: PipelineRunStatusUpdate) -> None:
    for name, val in [
        ("city_count", update.city_count),
        ("raw_response_count", update.raw_response_count),
        ("gold_row_count", update.gold_row_count),
    ]:
        if val is not None and val < 0:
            raise ValueError(f"{name} must be >= 0, got {val}")


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
        _validate_create_args(run_id, history_hours, window_start_utc, window_end_utc)

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
        _validate_status_value(update.status)

        record = self._runs_store.get(run_id)
        if not record:
            log.error("Failed to update status: run_id not found", extra={"run_id": run_id})
            raise KeyError(f"Pipeline run '{run_id}' not found.")

        if record.status in TERMINAL_STATUSES:
            raise ValueError(
                f"Cannot transition run '{run_id}' from terminal status '{record.status}' to '{update.status}'."
            )

        _validate_counters(update)

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

    def list(self, limit: int = 10) -> list[PipelineRunRecord]:
        """Return the most recent pipeline runs, up to the requested limit."""
        if limit <= 0:
            raise ValueError("limit must be greater than 0.")

        runs = list(self._runs_store.values())
        runs.sort(key=lambda run: run.created_at, reverse=True)
        return runs[:limit]


class PostgresPipelineRunRepository:
    """Postgres-backed repository implementing the same contract as InMemoryPipelineRunRepository.

    Each method opens its own short-lived connection via `pipeline.common.db.get_connection()`
    and commits/rolls back as its own unit of work — this is intentionally independent from the
    connection used for raw/gold writes during extract/load (see the transaction-boundary
    write-up in docs/architecture/postgresql_schema_design.md).
    """

    def create(
        self,
        run_id: str,
        source: str,
        history_hours: int,
        window_start_utc: datetime,
        window_end_utc: datetime,
    ) -> int:
        _validate_create_args(run_id, history_hours, window_start_utc, window_end_utc)

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pipeline_runs (
                        run_id, source, history_hours, window_start_utc, window_end_utc
                    )
                    VALUES (
                        %(run_id)s, %(source)s, %(history_hours)s,
                        %(window_start_utc)s, %(window_end_utc)s
                    )
                    RETURNING pipeline_run_id;
                    """,
                    {
                        "run_id": run_id,
                        "source": source,
                        "history_hours": history_hours,
                        "window_start_utc": window_start_utc,
                        "window_end_utc": window_end_utc,
                    },
                )
                (pipeline_run_id,) = cur.fetchone()
            conn.commit()
        except psycopg.errors.UniqueViolation:
            conn.rollback()
            log.error("Failed to create pipeline run: run_id already exists", extra={"run_id": run_id})
            raise ValueError(f"Pipeline run with run_id='{run_id}' already exists.") from None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        log.info(
            "Pipeline run record created",
            extra={
                "run_id": run_id,
                "pipeline_run_id": pipeline_run_id,
                "status": "running",
                "source": source,
            },
        )
        return pipeline_run_id

    def update_status(self, run_id: str, update: PipelineRunStatusUpdate) -> None:
        _validate_status_value(update.status)

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM pipeline_runs WHERE run_id = %s;", (run_id,))
                row = cur.fetchone()
                if row is None:
                    log.error("Failed to update status: run_id not found", extra={"run_id": run_id})
                    raise KeyError(f"Pipeline run '{run_id}' not found.")

                (current_status,) = row
                if current_status in TERMINAL_STATUSES:
                    raise ValueError(
                        f"Cannot transition run '{run_id}' from terminal status "
                        f"'{current_status}' to '{update.status}'."
                    )

                _validate_counters(update)

                finished_at = update.finished_at
                if finished_at is None and update.status in TERMINAL_STATUSES:
                    finished_at = datetime.now(timezone.utc)

                cur.execute(
                    """
                    UPDATE pipeline_runs
                    SET status = %(status)s,
                        city_count = COALESCE(%(city_count)s, city_count),
                        raw_response_count = COALESCE(%(raw_response_count)s, raw_response_count),
                        gold_row_count = COALESCE(%(gold_row_count)s, gold_row_count),
                        error_message = COALESCE(%(error_message)s, error_message),
                        finished_at = COALESCE(%(finished_at)s, finished_at)
                    WHERE run_id = %(run_id)s;
                    """,
                    {
                        "run_id": run_id,
                        "status": update.status,
                        "city_count": update.city_count,
                        "raw_response_count": update.raw_response_count,
                        "gold_row_count": update.gold_row_count,
                        "error_message": update.error_message,
                        "finished_at": finished_at,
                    },
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        log.info(
            "Pipeline run status updated",
            extra={
                "run_id": run_id,
                "status": update.status,
                "city_count": update.city_count,
                "raw_response_count": update.raw_response_count,
                "gold_row_count": update.gold_row_count,
            },
        )

    def get(self, run_id: str) -> PipelineRunRecord | None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"{_SELECT_SQL} WHERE run_id = %s;", (run_id,))
                row = cur.fetchone()
        finally:
            conn.close()

        return _row_to_record(row) if row is not None else None

    def list(self, limit: int = 10) -> list[PipelineRunRecord]:
        if limit <= 0:
            raise ValueError("limit must be greater than 0.")

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"{_SELECT_SQL} ORDER BY created_at DESC LIMIT %s;", (limit,))
                rows = cur.fetchall()
        finally:
            conn.close()

        return [_row_to_record(row) for row in rows]


# Default module-level repository instance (used when Postgres isn't configured)
_default_repository = InMemoryPipelineRunRepository()


def _resolve_repository() -> InMemoryPipelineRunRepository | PostgresPipelineRunRepository:
    """Pick the Postgres-backed repository when DATABASE_URL is configured, else in-memory.

    Checked live (not cached at import time) so tests can monkeypatch
    `pipeline.common.config.settings.database_url` the same way other settings are patched.
    """
    if settings.database_url.get_secret_value().strip():
        return PostgresPipelineRunRepository()
    return _default_repository


def create_pipeline_run(
    run_id: str,
    source: str,
    history_hours: int,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> int:
    """Creates a new pipeline run record."""
    return _resolve_repository().create(
        run_id=run_id,
        source=source,
        history_hours=history_hours,
        window_start_utc=window_start_utc,
        window_end_utc=window_end_utc,
    )


def update_pipeline_run_status(run_id: str, update: PipelineRunStatusUpdate) -> None:
    """Updates the status and counters of an existing pipeline run."""
    _resolve_repository().update_status(run_id=run_id, update=update)


def list_pipeline_runs(limit: int = 10) -> list[PipelineRunRecord]:
    """Return the most recent pipeline runs, up to the requested limit.

    Reads from Postgres when DATABASE_URL is configured, so history persists across
    CLI invocations; falls back to the in-process repository otherwise.
    """
    return _resolve_repository().list(limit=limit)
