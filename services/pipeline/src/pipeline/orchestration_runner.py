from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd

from pipeline.common.logging import get_logger
from pipeline.extract.cities import City
from pipeline.extract.openweather_air_pollution import RawAirPollutionRecord
from pipeline.load.storage import PublishResult

log = get_logger(__name__)

ExtractStage = Callable[..., "tuple[list[RawAirPollutionRecord], int]"]
TransformStage = Callable[..., pd.DataFrame]
LoadStage = Callable[..., PublishResult]


@dataclass(frozen=True)
class PipelineRunResult:
    pipeline_run_id: int
    run_id: str
    source: str
    history_hours: int
    status: str
    raw_records: list[RawAirPollutionRecord]
    gold_path: Path | None
    azure_blob_path: str | None
    postgres_table: str | None
    city_count: int
    raw_response_count: int
    gold_row_count: int
    rows: int


def run_pipeline(
    cities: list[City],
    raw_dir: Path,
    gold_dir: Path,
    start: datetime,
    end: datetime,
    run_id: str,
    pipeline_run_id: int,
    source: str,
    history_hours: int,
    table_name: str = "air_pollution_gold",
    *,
    extract: ExtractStage,
    transform: TransformStage,
    load: LoadStage,
) -> PipelineRunResult:
    """Runs the extract, transform, and load stages in order for one pipeline run.

    Each stage is called only after the previous one has completed successfully.
    If a stage raises, the exception is logged with the stage name and re-raised
    unchanged, and no later stage is called.
    """
    log.info(
        "Runner starting",
        extra={"run_id": run_id, "pipeline_run_id": pipeline_run_id, "city_count": len(cities)},
    )

    try:
        raw_records, city_count = extract(
            raw_dir=raw_dir,
            cities=cities,
            start=start,
            end=end,
            run_id=run_id,
            pipeline_run_id=pipeline_run_id,
        )
    except Exception:
        log.exception(
            "Extract stage failed",
            extra={"run_id": run_id, "pipeline_run_id": pipeline_run_id},
        )
        raise

    try:
        gold_df = transform(raw_records=raw_records)
    except Exception:
        log.exception(
            "Transform stage failed",
            extra={"run_id": run_id, "pipeline_run_id": pipeline_run_id, "raw_response_count": len(raw_records)},
        )
        raise

    if not gold_df.empty:
        gold_df["pipeline_run_id"] = pipeline_run_id

    try:
        publish_result = load(
            gold_df=gold_df,
            gold_dir=gold_dir,
            run_id=run_id,
            table_name=table_name,
        )
    except Exception:
        log.exception(
            "Load stage failed",
            extra={"run_id": run_id, "pipeline_run_id": pipeline_run_id, "gold_row_count": len(gold_df)},
        )
        raise

    log.info(
        "Runner finished",
        extra={
            "run_id": run_id,
            "pipeline_run_id": pipeline_run_id,
            "city_count": city_count,
            "raw_response_count": len(raw_records),
            "gold_row_count": len(gold_df),
        },
    )

    return PipelineRunResult(
        pipeline_run_id=pipeline_run_id,
        run_id=run_id,
        source=source,
        history_hours=history_hours,
        status="succeeded",
        raw_records=raw_records,
        gold_path=publish_result.gold_path,
        azure_blob_path=publish_result.azure_blob_path,
        postgres_table=publish_result.table_name,
        city_count=city_count,
        raw_response_count=len(raw_records),
        gold_row_count=len(gold_df),
        rows=len(gold_df),
    )
