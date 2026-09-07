"""
Scheduler entrypoint for scheduled/automated pipeline runs.

Runs the shared pipeline orchestration job and returns an exit code
so external schedulers (e.g., GitHub Actions cron) can detect success/failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure pipeline package is importable when run as a script
SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pipeline.common.logging import get_logger
from pipeline.orchestration import run_pipeline_job

log = get_logger(__name__)

# Marks runs as coming from the scheduler (stored in pipeline_runs.source)
SCHEDULER_SOURCE = "scheduler"


def main() -> int:
    log.info("Scheduler entrypoint invoked", extra={"source": SCHEDULER_SOURCE})

    try:
        # No history_hours here — run_pipeline_job uses settings.history_hours
        result = run_pipeline_job(source=SCHEDULER_SOURCE)
    except Exception:
        # run_pipeline_job already logs and marks the run failed
        log.exception("Scheduled pipeline run failed", extra={"source": SCHEDULER_SOURCE})
        return 1

    log.info(
        "Scheduled pipeline run finished",
        extra={
            "run_id": result.run_id,
            "pipeline_run_id": result.pipeline_run_id,
            "gold_row_count": result.rows,
            "postgres_table": result.postgres_table,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
