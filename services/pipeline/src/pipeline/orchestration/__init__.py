from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import psycopg

from pipeline.common.config import settings
from pipeline.common.db import get_connection
from pipeline.common.logging import get_logger
from pipeline.extract.cities import City, read_cities
from pipeline.extract.geocoding import GEOCODING_URL, geocode_city
from pipeline.extract.openweather_air_pollution import (
    OPENWEATHER_AIR_POLLUTION_URL,
    RawAirPollutionRecord,
    fetch_air_pollution_history,
    to_transform_input,
)
from pipeline.load.cities import upsert_cities
from pipeline.load.raw import save_raw_air_pollution_response, save_raw_geocoding_response
from pipeline.load.storage import DEFAULT_TABLE_NAME, PublishResult, publish_outputs
from pipeline.orchestration_runner import (
    PipelineRunResult,
    PipelineStageProgress,
    run_pipeline,
)
from pipeline.run_tracking import (
    PipelineRunStatusUpdate,
    create_pipeline_run,
    update_pipeline_run_status,
)
from pipeline.transform.transform import transform_raw_response

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
    raw_dir: Path,
    cities: list[City],
    start: datetime,
    end: datetime,
    run_id: str,
    pipeline_run_id: int,
    conn: psycopg.Connection | None = None,
) -> tuple[list[RawAirPollutionRecord], int]:
    raw_records: list[RawAirPollutionRecord] = []

    if conn is not None:
        upsert_cities(conn, cities)

    for city in cities:
        coords = geocode_city(
            raw_dir=raw_dir,
            city=city.city,
            country_code=city.country_code,
            state=city.state,
        )

        if coords is None:
            log.warning(
                "Geocoding failed or returned no coordinates, skipping city",

                extra={
                    "run_id": run_id,
                    "pipeline_run_id": pipeline_run_id,
                    "city": city.city,
                    "country_code": city.country_code,
                    "state": city.state,
                },
            )
            continue

        if conn is not None and coords.payload is not None:
            save_raw_geocoding_response(
                conn,
                {
                    "pipeline_run_id": pipeline_run_id,
                    "city_id": city.city_id,
                    "city_name": city.city_name,
                    "country_code": city.country_code,
                    "state_code": city.state_code,
                    "lat": coords.lat,
                    "lon": coords.lon,
                    "coordinate_source": coords.source,
                    "endpoint": GEOCODING_URL,
                    "retrieved_at": datetime.now(timezone.utc),
                    "http_status": coords.http_status,
                    "payload": coords.payload,
                },
            )

        raw_record = fetch_air_pollution_history(
            raw_dir=raw_dir,
            city_id=city.city_id,
            city=city.city,
            country_code=city.country_code,
            state_code=city.state,
            lat=coords.lat,
            lon=coords.lon,
            start=start,
            end=end,
            run_id=run_id,
            pipeline_run_id=pipeline_run_id,
        )
        raw_records.append(raw_record)

        if conn is not None and raw_record.raw_response is not None:
            save_raw_air_pollution_response(
                conn,
                {
                    "pipeline_run_id": pipeline_run_id,
                    "city_id": raw_record.city_id,
                    "city_name": raw_record.city,
                    "country_code": raw_record.country_code,
                    "state_code": raw_record.state_code,
                    "coordinate_source": coords.source,
                    "lat": raw_record.lat,
                    "lon": raw_record.lon,
                    "start": raw_record.start,
                    "end": raw_record.end,
                    "endpoint": OPENWEATHER_AIR_POLLUTION_URL,
                    "retrieved_at": raw_record.retrieved_at,
                    "http_status": 200,
                    "payload": raw_record.raw_response,
                },
            )

    return raw_records, len(cities)


def run_transform_stage(raw_records: list[RawAirPollutionRecord]) -> pd.DataFrame:
    transformed_records: list[dict] = []
    for record in raw_records:
        envelope = to_transform_input(record)
        clean_records = transform_raw_response(envelope)
        transformed_records.extend(clean_records)

    return pd.DataFrame(transformed_records)


def run_load_stage(
    gold_df: pd.DataFrame,
    gold_dir: Path,
    run_id: str,
    table_name: str = DEFAULT_TABLE_NAME,
    conn: psycopg.Connection | None = None,
) -> PublishResult:
    return publish_outputs(
        gold_df=gold_df,
        gold_dir=gold_dir,
        run_id=run_id,
        table_name=table_name,
        conn=conn,
    )


def run_pipeline_job(source: str = "openweather", history_hours: int | None = None) -> PipelineRunResult:
    resolved_history_hours = int(settings.history_hours if history_hours is None else history_hours)
    raw_dir, gold_dir = ensure_output_directories()
    start, end = build_runtime_window(resolved_history_hours)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

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

    progress = PipelineStageProgress()

    conn: psycopg.Connection | None = None
    if settings.database_url.get_secret_value().strip():
        conn = get_connection()
    else:
        log.info(
            "DATABASE_URL not configured; Postgres writes will be skipped for this run",
            extra={"run_id": run_id, "pipeline_run_id": pipeline_run_id},
        )

    try:
        cities_path = Path(settings.cities_file) if settings.cities_source == "file" else None
        cities = read_cities(cities_path)

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
            conn=conn,
            extract=run_extract_stage,
            transform=run_transform_stage,
            load=run_load_stage,
            progress=progress,
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
            extra={
                "run_id": run_id,
                "pipeline_run_id": pipeline_run_id,
                "source": source,
                "city_count": progress.city_count,
                "raw_response_count": progress.raw_response_count,
                "gold_row_count": progress.gold_row_count,
            },
        )
        update_pipeline_run_status(
            run_id,
            PipelineRunStatusUpdate(
                status="failed",
                city_count=progress.city_count,
                raw_response_count=progress.raw_response_count,
                gold_row_count=progress.gold_row_count,
                error_message=str(exc),
                finished_at=datetime.now(timezone.utc),
            ),
        )
        raise
    finally:
        if conn is not None:
            conn.close()