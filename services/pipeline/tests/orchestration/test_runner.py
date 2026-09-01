from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from pipeline.extract.cities import City
from pipeline.load.storage import PublishResult
from pipeline.orchestration_runner import PipelineStageProgress, run_pipeline


def make_city(city_id: str = "city-1") -> City:
    return City(
        city_name="Testville",
        country_code="US",
        city_id=city_id,
        timezone="UTC",
        active=True,
    )


def run_it(tmp_path, *, extract, transform, load, pipeline_run_id=1, progress=None):
    return run_pipeline(
        cities=[make_city()],
        raw_dir=tmp_path / "raw",
        gold_dir=tmp_path / "gold",
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, tzinfo=timezone.utc),
        run_id="20260101T000000Z",
        pipeline_run_id=pipeline_run_id,
        source="openweather",
        history_hours=24,
        extract=extract,
        transform=transform,
        load=load,
        progress=progress if progress is not None else PipelineStageProgress(),
    )


def test_run_pipeline_calls_stages_in_order(tmp_path):
    calls: list[str] = []

    def fake_extract(**kwargs):
        calls.append("extract")
        return [], 1

    def fake_transform(**kwargs):
        calls.append("transform")
        return pd.DataFrame()

    def fake_load(**kwargs):
        calls.append("load")
        return PublishResult()

    run_it(tmp_path, extract=fake_extract, transform=fake_transform, load=fake_load)

    assert calls == ["extract", "transform", "load"]


def test_run_pipeline_returns_expected_result_shape_on_success(tmp_path):
    fake_records = ["record-a", "record-b"]
    fake_gold_df = pd.DataFrame({"aqi": [1, 2]})
    fake_publish_result = PublishResult(
        gold_path=tmp_path / "gold" / "run.parquet",
        azure_blob_path=None,
        table_name="air_pollution_gold",
        rows=2,
        parquet_error=None,
    )

    result = run_it(
        tmp_path,
        extract=lambda **kwargs: (fake_records, 2),
        transform=lambda **kwargs: fake_gold_df.copy(),
        load=lambda **kwargs: fake_publish_result,
        pipeline_run_id=7,
    )

    assert result.status == "succeeded"
    assert result.pipeline_run_id == 7
    assert result.run_id == "20260101T000000Z"
    assert result.source == "openweather"
    assert result.history_hours == 24
    assert result.raw_records == fake_records
    assert result.city_count == 2
    assert result.raw_response_count == 2
    assert result.gold_row_count == 2
    assert result.gold_path == fake_publish_result.gold_path
    assert result.azure_blob_path is None
    assert result.postgres_table == "air_pollution_gold"


def test_run_pipeline_stops_and_reports_on_stage_failure(tmp_path):
    calls: list[str] = []
    progress = PipelineStageProgress()

    def fake_extract(**kwargs):
        calls.append("extract")
        return ["record-a"], 1

    def fake_transform(**kwargs):
        calls.append("transform")
        raise ValueError("transform blew up")

    def fake_load(**kwargs):
        calls.append("load")
        return PublishResult()

    with pytest.raises(ValueError, match="transform blew up"):
        run_it(tmp_path, extract=fake_extract, transform=fake_transform, load=fake_load, progress=progress)

    assert calls == ["extract", "transform"]
    assert progress.city_count == 1
    assert progress.raw_response_count == 1
    assert progress.gold_row_count is None
