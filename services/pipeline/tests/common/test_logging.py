"""Unit tests for the common logging infrastructure and configuration integration."""

from __future__ import annotations

import logging
import uuid

import pytest

from pipeline.common.logging import ContextFormatter, get_logger


def _get_unique_logger_name() -> str:
    """Generate a unique logger identifier to prevent cross-test handler contamination."""
    return f"test_logger_{uuid.uuid4().hex}"


def test_logger_defaults_to_info_level() -> None:
    """Verify that logger initializes with default INFO level when no overrides exist."""
    test_log = get_logger(_get_unique_logger_name())
    assert test_log.getEffectiveLevel() == logging.INFO


def test_logger_respects_debug_level_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that setting log_level to DEBUG updates the logger effective level accordingly."""
    from pipeline.common import config

    monkeypatch.setattr(config.settings, "log_level", "DEBUG")

    test_log = get_logger(_get_unique_logger_name())
    assert test_log.getEffectiveLevel() == logging.DEBUG


def test_logger_case_insensitive_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that lowercase log level names are correctly normalized and parsed."""
    from pipeline.common import config

    monkeypatch.setattr(config.settings, "log_level", "warning")

    test_log = get_logger(_get_unique_logger_name())
    assert test_log.getEffectiveLevel() == logging.WARNING


def test_logger_falls_back_to_info_on_invalid_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify graceful fallback to INFO level when an invalid level name is encountered."""
    from pipeline.common import config

    monkeypatch.setattr(config.settings, "log_level", "INVALID_LEVEL_NAME")

    test_log = get_logger(_get_unique_logger_name())
    assert test_log.getEffectiveLevel() == logging.INFO


def test_context_formatter_appends_extra_fields() -> None:
    """Verify that ContextFormatter properly appends custom extra fields to the message."""
    formatter = ContextFormatter(fmt="[%(levelname)s] %(message)s")
    record = logging.LogRecord(
        name="test_record",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Extraction completed",
        args=(),
        exc_info=None,
    )
    # Inject context extras
    record.__dict__["run_id"] = "run_123"
    record.__dict__["city"] = "Las Vegas"

    formatted_output = formatter.format(record)
    assert formatted_output == "[INFO] Extraction completed | run_id=run_123 city=Las Vegas"


def test_context_formatter_without_extras() -> None:
    """Verify that ContextFormatter produces clean output when no custom extras are supplied."""
    formatter = ContextFormatter(fmt="[%(levelname)s] %(message)s")
    record = logging.LogRecord(
        name="test_record",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Standard log message",
        args=(),
        exc_info=None,
    )

    formatted_output = formatter.format(record)
    assert formatted_output == "[INFO] Standard log message"