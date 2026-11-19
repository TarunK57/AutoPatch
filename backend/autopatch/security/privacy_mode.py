from __future__ import annotations

import os
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from autopatch.core.exceptions import AutoPatchException


class PrivacyModeViolationError(AutoPatchException):
    """Raised when an external LLM or network call is attempted while Privacy Mode is active."""
    pass


class PrivacyGuard:
    """
    Guarantees zero external network or LLM API calls when Privacy Mode is active.
    Restricts defect detection and patch generation strictly to local AST rules,
    local linters, and deterministic template fixes.
    """

    _global_privacy_mode: bool = os.environ.get("AUTOPATCH_PRIVACY_MODE", "0") in ("1", "true", "yes")

    @classmethod
    def is_privacy_mode_active(cls, request_override: Optional[bool] = None) -> bool:
        """Returns True if Privacy Mode is active for the current request or globally."""
        if request_override is not None:
            return request_override
        return cls._global_privacy_mode

    @classmethod
    def set_global_privacy_mode(cls, enabled: bool) -> None:
        """Sets global privacy mode."""
        cls._global_privacy_mode = enabled

    @classmethod
    def assert_llm_allowed(cls, privacy_mode_active: bool = False, caller: str = "LLM_CALL") -> None:
        """
        Asserts that an LLM call is permissible under current privacy constraints.
        Raises PrivacyModeViolationError if Privacy Mode is enabled.
        """
        if privacy_mode_active or cls._global_privacy_mode:
            raise PrivacyModeViolationError(
                f"External LLM invocation '{caller}' is strictly forbidden while Privacy Mode is active. "
                "AutoPatch must operate using local AST rules, linters, and deterministic template fixes only."
            )
