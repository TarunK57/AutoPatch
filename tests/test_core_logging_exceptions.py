"""Unit tests for structured JSON logging and exception hierarchy."""

import io
import json
import logging
from autopatch.core.exceptions import (
    AutoPatchError,
    InvariantViolationError,
    UnauthorizedPatchApplicationError,
    UnconfirmedBugError,
    UnverifiedPatchError,
    TestModificationForbiddenError,
    SecretLeakageError,
    SandboxSecurityError,
)
from autopatch.core.logging import JSONFormatter, get_logger


def test_exception_hierarchy_and_serialization():
    """Verify exception inheritance and serialization to dict."""
    exc = UnauthorizedPatchApplicationError(
        "Human approval is mandatory", details={"patch_id": "p-123", "action": "apply"}
    )
    assert isinstance(exc, InvariantViolationError)
    assert isinstance(exc, AutoPatchError)

    d = exc.to_dict()
    assert d["error_type"] == "UnauthorizedPatchApplicationError"
    assert d["message"] == "Human approval is mandatory"
    assert d["details"]["patch_id"] == "p-123"


def test_structured_json_logging():
    """Verify that JSONFormatter outputs valid JSON with all required fields."""
    stream = io.StringIO()
    logger = get_logger("test_structured_logger", level=logging.DEBUG, stream=stream)

    logger.info("Test event occurred", extra={"data": {"user_id": "usr_99", "status": "active"}})

    log_output = stream.getvalue().strip()
    parsed = json.loads(log_output)

    assert parsed["level"] == "INFO"
    assert parsed["service"] == "autopatch"
    assert parsed["logger"] == "test_structured_logger"
    assert parsed["message"] == "Test event occurred"
    assert parsed["data"]["user_id"] == "usr_99"
    assert "timestamp" in parsed
    assert "module" in parsed
