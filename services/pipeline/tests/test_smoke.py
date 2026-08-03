"""Smoke test for the pipeline test harness.

This does not test any business logic yet -- there isn't any. It
exists to confirm that the pipeline package is importable and that the
test harness (conftest.py + pytest config) is wired up correctly.
"""


def test_pipeline_package_imports():
    import pipeline

    assert pipeline is not None
