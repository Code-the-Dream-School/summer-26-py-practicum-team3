"""Logging infrastructure module for structured pipeline logging."""

from __future__ import annotations

import logging
import sys

from pipeline.common.config import settings

# Baseline set of standard LogRecord attributes to ignore when parsing extra fields.
# Note: 'message' and 'asctime' are populated dynamically during Formatter.format() and must be added explicitly.
_STANDARD_RECORD_ATTRS = (
    set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())
    | {"message", "asctime"}
)


class ContextFormatter(logging.Formatter):
    """Formatter that appends contextual 'extra' fields (e.g., run_id, pipeline_run_id)."""

    def format(self, record: logging.LogRecord) -> str:
        base_msg = super().format(record)

        # Extract only custom fields passed via extra={...}
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _STANDARD_RECORD_ATTRS and not k.startswith("_")
        }

        if extras:
            context_str = " ".join(f"{k}={v}" for k, v in extras.items())
            return f"{base_msg} | {context_str}"

        return base_msg


def get_logger(name: str) -> logging.Logger:
    """Configures and returns a logger with the shared ContextFormatter."""
    logger = logging.getLogger(name)

    # Attach handler only once
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = ContextFormatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Update log level on every call
    level_name = getattr(settings, "log_level", "INFO").upper()
    level = getattr(logging, level_name, None)

    if level is None:
        logger.setLevel(logging.INFO)
        logger.warning(f"Invalid log level '{level_name}' configured. Falling back to INFO.")
    else:
        logger.setLevel(level)

    return logger