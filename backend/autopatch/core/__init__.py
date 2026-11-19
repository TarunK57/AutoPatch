"""Core domain primitives, schemas, exceptions, and structured logging."""

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
from autopatch.core.models import (
    Severity,
    BugStatus,
    ApprovalStatus,
    ConfidenceScore,
    ReproductionEvidence,
    BugReport,
    Patch,
    VerificationEvidence,
    ApprovalDecision,
    ReviewBundle,
    AuditLogEntry,
)

__all__ = [
    "AutoPatchError",
    "InvariantViolationError",
    "UnauthorizedPatchApplicationError",
    "UnconfirmedBugError",
    "UnverifiedPatchError",
    "TestModificationForbiddenError",
    "SecretLeakageError",
    "SandboxSecurityError",
    "Severity",
    "BugStatus",
    "ApprovalStatus",
    "ConfidenceScore",
    "ReproductionEvidence",
    "BugReport",
    "Patch",
    "VerificationEvidence",
    "ApprovalDecision",
    "ReviewBundle",
    "AuditLogEntry",
]
