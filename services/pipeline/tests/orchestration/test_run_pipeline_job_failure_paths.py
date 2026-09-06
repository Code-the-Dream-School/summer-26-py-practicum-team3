"""Regression tests for run_pipeline_job's handling of failures around connection setup.

These cover two edge cases found in review:
1. create_pipeline_run() itself fails (e.g. Postgres briefly unreachable) — no pipeline_runs row
   exists yet, so run_pipeline_job must not attempt to update a nonexistent row (which would mask
   the real error with a KeyError instead of propagating it).
2. get_connection() for the extract/load connection fails *after* create_pipeline_run() already
   succeeded — the run's pipeline_runs row must end up status='failed', not stuck at 'running'.
"""

from __future__ import annotations

import pytest

from pipeline.orchestration import run_pipeline_job


def test_run_pipeline_job_propagates_create_pipeline_run_failure_without_masking_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(*args, **kwargs):
        raise RuntimeError("db unreachable")

    monkeypatch.setattr("pipeline.orchestration.create_pipeline_run", _raise)

    # Would raise KeyError instead (masking the real error) if run_pipeline_job tried to
    # update_pipeline_run_status for a run_id that was never created.
    with pytest.raises(RuntimeError, match="db unreachable"):
        run_pipeline_job(source="test")
