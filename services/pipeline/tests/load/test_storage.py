"""Unit tests for the Gold storage and Parquet secondary export layer."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from pipeline.load.storage import PublishResult, publish_outputs

# ============================================================================
# 1. Fixtures
# ============================================================================

@pytest.fixture
def sample_gold_df():
    """Returns a non-empty sample Gold DataFrame."""
    return pd.DataFrame(
        [
            {
                "city_id": "us-san-francisco-ca",
                "observed_at": "2026-08-15T12:00:00Z",
                "aqi": 2,
                "pm2_5": 8.45,
                "pipeline_run_id": "pipeline-2026-08-15-001",
            }
        ]
    )


# ============================================================================
# 2. Validation & Security Tests
# ============================================================================

@pytest.mark.parametrize("invalid_run_id", ["../escape", "run/id", "run:id", "run*id", "", "   "])
def test_publish_outputs_invalid_run_id_raises_error(tmp_path: Path, sample_gold_df: pd.DataFrame, invalid_run_id: str):
    """Unsafe run_id characters must raise ValueError to prevent path traversal."""
    with pytest.raises(ValueError, match="Invalid run_id"):
        publish_outputs(
            gold_df=sample_gold_df,
            gold_dir=tmp_path,
            run_id=invalid_run_id,
            table_name="air_pollution_gold",
        )


# ============================================================================
# 3. Functional Execution & Output Publishing Tests
# ============================================================================

def test_publish_outputs_success(tmp_path: Path, sample_gold_df: pd.DataFrame):
    """Verifies successful write matching orchestration field names."""
    run_id = "run-2026-08-15-001"
    result = publish_outputs(
        gold_df=sample_gold_df,
        gold_dir=tmp_path,
        run_id=run_id,
        table_name="air_pollution_gold",
    )

    assert isinstance(result, PublishResult)
    assert result.rows == 1
    assert result.table_name == "air_pollution_gold"
    assert result.parquet_error is None
    assert result.gold_path is not None
    assert result.gold_path.exists()
    assert result.gold_path.name == "run-2026-08-15-001_air_pollution_gold.parquet"

    # Verify content readability
    df_read = pd.read_parquet(result.gold_path)
    assert len(df_read) == 1
    assert df_read.iloc[0]["city_id"] == "us-san-francisco-ca"


def test_publish_outputs_empty_df_skips_file_creation(tmp_path: Path):
    """Verifies that empty dataframe sets gold_path=None and leaves directory clean."""
    empty_df = pd.DataFrame()
    run_id = "run-2026-08-15-002"

    result = publish_outputs(
        gold_df=empty_df,
        gold_dir=tmp_path,
        run_id=run_id,
        table_name="air_pollution_gold",
    )

    assert result.rows == 0
    assert result.table_name == "air_pollution_gold"
    assert result.gold_path is None
    assert result.parquet_error is None
    assert list(tmp_path.glob("*.parquet")) == []


def test_publish_outputs_none_gold_dir(sample_gold_df: pd.DataFrame):
    """Verifies safe execution when secondary parquet directory is disabled."""
    result = publish_outputs(
        gold_df=sample_gold_df,
        gold_dir=None,
        run_id="run-2026-08-15-003",
        table_name="air_pollution_gold",
    )

    assert result.rows == 1
    assert result.table_name == "air_pollution_gold"
    assert result.gold_path is None
    assert result.parquet_error is None


# ============================================================================
# 4. Error Isolation & File Integrity Tests
# ============================================================================

def test_publish_outputs_preserves_preexisting_file_on_write_failure(
    tmp_path: Path, sample_gold_df: pd.DataFrame
):
    """Verifies that a write failure does not corrupt or wipe an existing file from a prior run."""
    run_id = "run-2026-08-15-001"
    target_parquet = tmp_path / f"{run_id}_air_pollution_gold.parquet"
    tmp_parquet = tmp_path / f"{run_id}_air_pollution_gold.parquet.tmp"

    # 1. Arrange: Create an initial valid file on disk
    initial_df = pd.DataFrame([{"city_id": "us-seattle-wa", "observed_at": "2026-08-15T10:00:00Z"}])
    initial_df.to_parquet(target_parquet, index=False)
    initial_content_checksum = target_parquet.read_bytes()

    # 2. Act: Attempt second publish with forced failure during serialization
    def faulty_to_parquet(path, *args, **kwargs):
        Path(path).write_text("partial corrupted chunk")
        raise PermissionError("Access denied during parquet file write")

    with patch.object(pd.DataFrame, "to_parquet", side_effect=faulty_to_parquet):
        result = publish_outputs(
            gold_df=sample_gold_df,
            gold_dir=tmp_path,
            run_id=run_id,
            table_name="air_pollution_gold",
        )

    # 3. Assert: Result state reflects failure
    assert result.gold_path is None
    assert result.parquet_error is not None
    assert "PermissionError" in result.parquet_error or "Access denied" in result.parquet_error

    # 4. Assert: Disk state remains clean and uncorrupted
    assert target_parquet.exists(), "Pre-existing file must still exist"
    assert target_parquet.read_bytes() == initial_content_checksum, "Pre-existing file contents must remain identical"
    assert not tmp_parquet.exists(), "Temporary .tmp file must be cleaned up"