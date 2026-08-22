"""Shared pytest configuration for the pipeline test suite.

The pipeline package lives under services/pipeline/src/pipeline, but
tests are run from services/pipeline (see the CI workflow). This file
makes sure `src` is on sys.path so `import pipeline` works regardless
of how PYTHONPATH is configured for the caller.
"""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from pydantic import SecretStr

from pipeline.extract import geocoding


@pytest.fixture(autouse=True)
def configure_api_key(monkeypatch):
    monkeypatch.setattr(
        geocoding.settings,
        "openweather_api_key",
        SecretStr("test-api-key"),
    )
