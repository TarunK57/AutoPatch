"""Custom domain exceptions for AutoPatch enforcing core safety and architectural invariants."""

from typing import Optional, Dict, Any


class AutoPatchError(Exception):
    """Base exception for all AutoPatch domain errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


AutoPatchException = AutoPatchError


class InvariantViolationError(AutoPatchError):
    """Raised when an internal business invariant or rule is violated."""
    pass


# Rule 1: Trust
class UnauthorizedPatchApplicationError(InvariantViolationError):
    """Raised when an attempt is made to apply a patch without explicit human approval."""
    pass


class UnapprovedPatchActionError(InvariantViolationError):
    """Raised when patch action is requested on an unapproved review bundle."""
    pass


# Rule 2: Reproduce before repair
class UnconfirmedBugError(InvariantViolationError):
    """Raised when attempting repair on a bug that has not been confirmed via a failing reproduction test."""
    pass


class UnverifiedPatchError(InvariantViolationError):
    """Raised when a patch is asserted as verified without passing both the reproduction test and regression suite."""
    pass


# Rule 3: Minimal diffs
class TestModificationForbiddenError(InvariantViolationError):
    """Raised when a patch attempts to modify existing test files (Rule 3: Never modify existing tests)."""
    __test__ = False
    pass


class ExcessiveDiffScopeError(InvariantViolationError):
    """Raised when a patch modifies files outside the identified root cause scope."""
    pass


# Rule 4: Safety
class SecretLeakageError(InvariantViolationError):
    """Raised when unredacted secrets or credentials are detected before LLM ingestion."""
    pass


class SandboxSecurityError(InvariantViolationError):
    """Raised when a sandbox violates isolation rules (e.g. attempted network access, container escape)."""
    pass


# Rule 5: Honest uncertainty
class UncalibratedConfidenceError(InvariantViolationError):
    """Raised when a confidence score claims verification without corresponding verifiable test evidence."""
    pass


class JobCancelledError(AutoPatchError):
    """Raised when an active scan or bug repair job is cancelled."""
    pass


class CancellationToken:
    """Thread-safe cooperative cancellation token."""

    def __init__(self):
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def check_cancelled(self) -> None:
        if self._cancelled:
            raise JobCancelledError("Operation was cancelled by user request.")
