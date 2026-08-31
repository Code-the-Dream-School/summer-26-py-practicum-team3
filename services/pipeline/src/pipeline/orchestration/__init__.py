from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from pipeline.common.config import settings
from pipeline.common.logging import get_logger
from pipeline.extract.cities import City, read_cities
from pipeline.extract.geocoding import geocode_city
from pipeline.extract.openweather_air_pollution import RawAirPollutionRecord, fetch_air_pollution_history
from pipeline.load.storage import PublishResult, publish_outputs
from pipeline.orchestration_runner import PipelineRunResult, run_pipeline
from pipeline.run_tracking import PipelineRunStatusUpdate, create_pipeline_run, update_pipeline_run_status
from pipeline.transform.openweather_air_pollution_transform import build_gold_from_raw_records

__all__ = ["PipelineRunResult", "run_pipeline_job"]

log = get_logger(__name__)


def ensure_output_directories() -> tuple[Path, Path]:
    raw_dir = Path(settings.raw_dir)
    gold_dir = Path(settings.gold_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir, gold_dir


def build_runtime_window(history_hours: int) -> tuple[datetime, datetime]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=history_hours)
    return start, end


def run_extract_stage(
    raw_dir: Path, cities: list[City], start: datetime, end: datetime, run_id: str, pipeline_run_id: int
) -> tuple[list[RawAirPollutionRecord], int]:
    raw_records: list[RawAirPollutionRecord] = []

    for city in cities:
        coords = geocode_city(
            raw_dir=raw_dir,
            city=city.city,
            country_code=city.country_code,
            state=city.state,
        )
        raw_record = fetch_air_pollution_history(
            raw_dir=raw_dir,
            city=city.city,
            country_code=city.country_code,
            lat=coords.lat,
            lon=coords.lon,
            start=start,
            end=end,
            run_id=run_id,
            pipeline_run_id=pipeline_run_id,
        )
        raw_records.append(raw_record)

    return raw_records, len(cities)


def run_transform_stage(raw_records: list[RawAirPollutionRecord]) -> pd.DataFrame:
    return build_gold_from_raw_records(raw_records=raw_records)


def run_load_stage(
    gold_df: pd.DataFrame,
    gold_dir: Path,
    run_id: str,
    table_name: str = "air_pollution_gold",
) -> PublishResult:
    return publish_outputs(
        gold_df=gold_df,
        gold_dir=gold_dir,
        run_id=run_id,
        table_name=table_name,
    )


def run_pipeline_job(source: str = "openweather", history_hours: int | None = None) -> PipelineRunResult:
    resolved_history_hours = int(settings.history_hours if history_hours is None else history_hours)
    raw_dir, gold_dir = ensure_output_directories()
    start, end = build_runtime_window(resolved_history_hours)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cities_path = Path(settings.cities_file) if settings.cities_source == "file" else None
    cities = read_cities(cities_path)

    pipeline_run_id = create_pipeline_run(
        run_id=run_id,
        source=source,
        history_hours=resolved_history_hours,
        window_start_utc=start,
        window_end_utc=end,
    )

    log.info(
        "Pipeline starting",
        extra={
            "run_id": run_id,
            "pipeline_run_id": pipeline_run_id,
            "source": source,
            "history_hours": resolved_history_hours,
            "window_start_utc": start.isoformat(),
            "window_end_utc": end.isoformat(),
        },
    )

    try:
        result = run_pipeline(
            cities=cities,
            raw_dir=raw_dir,
            gold_dir=gold_dir,
            start=start,
            end=end,
            run_id=run_id,
            pipeline_run_id=pipeline_run_id,
            source=source,
            history_hours=resolved_history_hours,
            extract=run_extract_stage,
            transform=run_transform_stage,
            load=run_load_stage,
        )

        update_pipeline_run_status(
            run_id,
            PipelineRunStatusUpdate(
                status="succeeded",
                city_count=result.city_count,
                raw_response_count=result.raw_response_count,
                gold_row_count=result.gold_row_count,
                finished_at=datetime.now(timezone.utc),
            ),
        )

        log.info(
            "Pipeline succeeded",
            extra={
                "run_id": run_id,
                "pipeline_run_id": result.pipeline_run_id,
                "city_count": result.city_count,
                "raw_response_count": result.raw_response_count,
                "gold_row_count": result.gold_row_count,
                "postgres_table": result.postgres_table,
                "gold_path": str(result.gold_path) if result.gold_path is not None else None,
                "azure_blob_path": result.azure_blob_path,
            },
        )
        return result
    except Exception as exc:
        log.exception(
            "Pipeline failed",
            extra={"run_id": run_id, "pipeline_run_id": pipeline_run_id, "source": source},
        )
        update_pipeline_run_status(
            run_id,
            PipelineRunStatusUpdate(
                status="failed",
                error_message=str(exc),
                finished_at=datetime.now(timezone.utc),
            ),
        )
        raise