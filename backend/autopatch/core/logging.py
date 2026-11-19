"""Structured JSON logging configuration for AutoPatch."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """Formats log records as structured single-line JSON objects."""

    def __init__(self, service_name: str = "autopatch"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }

        # Include custom extra fields if provided
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            log_obj["data"] = record.extra_fields
        elif hasattr(record, "data") and isinstance(record.data, dict):
            log_obj["data"] = record.data

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


def get_logger(name: str, level: int = logging.INFO, stream: Optional[Any] = None) -> logging.Logger:
    """Creates or configures a structured logger with no duplicate handlers or hidden state.

    Args:
        name: Name of the logger.
        level: Logging level (defaults to INFO).
        stream: Target stream for output (defaults to sys.stdout).

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    # Avoid duplicate handlers if get_logger is called repeatedly
    if not any(isinstance(h.formatter, JSONFormatter) for h in logger.handlers):
        handler = logging.StreamHandler(stream or sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

    return logger
