import json
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    """Load a JSON fixture from the transform test fixtures directory."""

    def _load_fixture(filename):
        """Read and return a JSON fixture by filename."""
        fixture_path = FIXTURES_DIR / filename

        with fixture_path.open() as fixture_file:
            return json.load(fixture_file)

    return _load_fixture