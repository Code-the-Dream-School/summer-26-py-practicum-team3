from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.orchestration import run_extract_stage


def test_run_extract_stage_skips_failed_geocoding_with_context(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify geocoding failure logs a warning with run_id and pipeline_run_id in extra."""
    dummy_city = MagicMock()
    dummy_city.city = "Atlantis"
    dummy_city.country_code = "AQ"
    dummy_city.state = None

    now = datetime.now(timezone.utc)
    expected_run_id = "20260902T120000Z"
    expected_pipeline_run_id = 42

    caplog.set_level("WARNING")

    with (
        patch("pipeline.orchestration.geocode_city", return_value=None),
        patch("pipeline.orchestration.fetch_air_pollution_history") as mock_fetch,
    ):
        raw_records, total_cities = run_extract_stage(
            raw_dir=tmp_path,
            cities=[dummy_city],
            start=now,
            end=now,
            run_id=expected_run_id,
            pipeline_run_id=expected_pipeline_run_id,
        )

    # Fetch must not be called when geocoding fails
    mock_fetch.assert_not_called()
    assert raw_records == []
    assert total_cities == 1

    # Locate the geocoding failure warning log
    warning_records = [
        record
        for record in caplog.records
        if "Geocoding failed or returned no coordinates" in record.message
    ]
    assert len(warning_records) == 1

    record = warning_records[0]

    # Verify context and city fields attached via extra
    assert getattr(record, "run_id", None) == expected_run_id
    assert getattr(record, "pipeline_run_id", None) == expected_pipeline_run_id
    assert getattr(record, "city", None) == "Atlantis"
    assert getattr(record, "country_code", None) == "AQ"
    assert getattr(record, "state", None) is None