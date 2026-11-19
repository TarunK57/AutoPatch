"""Verifier subsystem for AutoPatch.

Provides:
- EphemeralSandbox: isolated sandbox execution enforcing network and host filesystem isolation.
- DifferentialChecker: behavioral invariance probing across untouched functions.
- OverfittingGuard: static literal and semantic overfitting detection.
- VerifierEngine: multi-stage 7-step verification, EPR calculation, and candidate ranking.
- Verification models: VerificationStatus, PatchVerificationResult, EnsembleEvaluation, etc.
"""

from autopatch.verifier.differential import DifferentialChecker
from autopatch.verifier.engine import VerifierEngine
from autopatch.verifier.models import (
    DifferentialCheckResult,
    EnsembleEvaluation,
    OverfittingCheckResult,
    PatchVerificationResult,
    SingleTestResult,
    SingleTestStatus,
    StructuredTestExecutionResult,
    VerificationStatus,
)
from autopatch.verifier.overfitting import OverfittingGuard
from autopatch.verifier.sandbox import EphemeralSandbox

__all__ = [
    "EphemeralSandbox",
    "DifferentialChecker",
    "OverfittingGuard",
    "VerifierEngine",
    "VerificationStatus",
    "SingleTestStatus",
    "SingleTestResult",
    "StructuredTestExecutionResult",
    "DifferentialCheckResult",
    "OverfittingCheckResult",
    "PatchVerificationResult",
    "EnsembleEvaluation",
]
