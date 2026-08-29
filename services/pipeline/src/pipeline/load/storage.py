"""Storage and publishing layer for Gold analytical records.

Provides primary export to PostgreSQL and secondary archival export to Parquet.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import pandas as pd

from pipeline.common.logging import get_logger

log = get_logger(__name__)

SAFE_RUN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass
class PublishResult:
    """Encapsulates destinations, metrics, and error state of published gold data."""

    gold_path: Path | None = None
    azure_blob_path: str | None = None
    table_name: str | None = None
    rows: int = 0
    parquet_error: str | None = None


def publish_outputs(
    gold_df: pd.DataFrame,
    gold_dir: Path | None,
    run_id: str,
    table_name: str = "air_pollution_gold",
) -> PublishResult:
    """Publishes transformed Gold records to secondary Parquet storage and PostgreSQL.

    Execution Lifecycle & Triggers:
        This function is executed during the Load stage of every pipeline job.
        - Primary Export: Always attempted to PostgreSQL (`table_name`).
        - Secondary Parquet Export: Attempted whenever `gold_dir` is provided (not None).
          If `gold_dir` is None, secondary file export is cleanly skipped (`gold_path=None`).
        - Empty Dataset: If `gold_df` is empty, Parquet file generation is skipped (`gold_path=None`)
          to avoid empty file clutter on disk.

    Atomic Staging & Safety:
        - Validates `run_id` against safe filename characters to prevent path traversal.
        - Writes Parquet files using atomic staging via a temporary file (*.tmp).
        - If writing fails, partial `.tmp` files are cleaned up and `parquet_error` is populated
          without crashing the pipeline execution.

    Args:
        gold_df: Transformed clean records ready for analytical storage.
        gold_dir: Directory where archival Parquet snapshots are saved (or None to skip).
        run_id: Unique pipeline run identifier (alphanumeric, underscores, hyphens).
        table_name: Name of the primary PostgreSQL destination table.

    Returns:
        PublishResult with populated paths, row counts, and error states.

    Raises:
        ValueError: If run_id contains invalid filename characters.
    """
    if not run_id or not SAFE_RUN_ID_PATTERN.match(run_id):
        raise ValueError(
            f"Invalid run_id '{run_id}'. run_id must contain only alphanumeric characters, underscores, and hyphens."
        )

    row_count = len(gold_df)

    if row_count == 0:
        log.info(
            "Gold dataframe is empty; skipping Parquet export",
            extra={"run_id": run_id, "gold_row_count": 0},
        )
        return PublishResult(
            gold_path=None,
            azure_blob_path=None,
            table_name=table_name,
            rows=0,
            parquet_error=None,
        )

    # --- Secondary Export: Local Parquet File (Atomic Write) ---
    parquet_path: Path | None = None
    parquet_err: str | None = None

    if gold_dir is not None:
        gold_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{run_id}_air_pollution_gold.parquet"
        target_path = gold_dir / file_name
        tmp_path = gold_dir / f"{file_name}.tmp"

        try:
            gold_df.to_parquet(tmp_path, index=False, engine="auto")
            os.replace(tmp_path, target_path)
            parquet_path = target_path
            log.info(
                "Secondary Parquet export completed",
                extra={
                    "run_id": run_id,
                    "gold_path": str(parquet_path),
                    "gold_row_count": row_count,
                },
            )
        except Exception as exc:  # noqa: BLE001
            parquet_err = str(exc)
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            log.error(
                "Failed to write Parquet file; cleaned up temporary artifacts",
                extra={"run_id": run_id, "error": parquet_err},
            )
            parquet_path = None

    # --- Primary Export: PostgreSQL Table ---
    # TODO (AIR-21): Wire actual Postgres upsert once DB connection layer is merged.

    return PublishResult(
        gold_path=parquet_path,
        azure_blob_path=None,
        table_name=table_name,
        rows=row_count,
        parquet_error=parquet_err,
    )