"""Core Pydantic domain models for AutoPatch.

Implements all contract invariants:
- Rule 1: Trust - Human approval required before patch application.
- Rule 2: Reproduce before repair - Bug confirmed only if reproduction fails; fix verified only if repro passes + 0 regressions.
- Rule 3: Minimal diffs - Existing tests can never be modified by a patch.
- Rule 4: Safety - Sandbox isolation required.
- Rule 5: Honest uncertainty - Confidence calibration and explicit explanation.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from autopatch.core.exceptions import (
    TestModificationForbiddenError,
    UnauthorizedPatchApplicationError,
    UnconfirmedBugError,
    UnverifiedPatchError,
    UncalibratedConfidenceError,
)


class Severity(str, Enum):
    """Bug severity rating with deterministic ordering and weighting."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        ranks = {
            Severity.LOW: 1,
            Severity.MEDIUM: 2,
            Severity.HIGH: 3,
            Severity.CRITICAL: 4,
        }
        return ranks[self]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank < other.rank

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank <= other.rank

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank > other.rank

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank >= other.rank


class BugStatus(str, Enum):
    """Lifecycle statuses for detected bugs."""

    DETECTED = "DETECTED"
    REPRODUCED_CONFIRMED = "REPRODUCED_CONFIRMED"
    UNCONFIRMED = "UNCONFIRMED"
    REPAIRING = "REPAIRING"
    REPAIRED_VERIFIED = "REPAIRED_VERIFIED"
    REPAIR_FAILED = "REPAIR_FAILED"


class ApprovalStatus(str, Enum):
    """Status of human approval on a patch review bundle."""

    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ReproductionEvidence(BaseModel):
    """Evidence demonstrating reproduction of a bug on unmodified code.

    Invariant (Rule 2): A bug is confirmed ONLY if the generated test fails
    (passed == False and exit_code != 0) on the buggy code.
    """

    test_code: str
    test_file_path: str
    execution_log: str
    exit_code: int
    passed: bool
    error_message: Optional[str] = None
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def confirms_bug(self) -> bool:
        """Returns True if and only if the test failed, proving reproduction of the bug."""
        return not self.passed and self.exit_code != 0


class ConfidenceScore(BaseModel):
    """Calibrated confidence assessment with explicit justification breakdown.

    Rule 5 (Honest Uncertainty): Confidence must be calibrated and explained.
    Never claim verification that was not run.
    """

    reproduction_score: float = Field(
        ge=0.0, le=1.0, description="1.0 if reproduction failed cleanly with expected assertion"
    )
    regression_score: float = Field(
        ge=0.0, le=1.0, description="1.0 if 0 regressions across full existing test suite"
    )
    minimal_diff_score: float = Field(
        ge=0.0, le=1.0, description="Score penalizing AST bloat and unrelated file edits"
    )
    llm_reasoning_score: float = Field(
        ge=0.0, le=1.0, description="Groundedness and consistency of root cause analysis"
    )
    overall: float = Field(ge=0.0, le=1.0, description="Deterministic calibrated aggregate score")
    calibration_notes: str = Field(
        min_length=10, description="Detailed explanation of score calculation, uncertainties, and assumptions"
    )

    @model_validator(mode="after")
    def validate_calibration(self) -> ConfidenceScore:
        # Invariant: Overall score cannot claim high confidence (>0.5) if reproduction failed or was not run
        if self.reproduction_score < 0.5 and self.overall > 0.5:
            raise UncalibratedConfidenceError(
                f"Overall confidence ({self.overall:.2f}) cannot exceed 0.5 without confirmed reproduction (reproduction_score={self.reproduction_score:.2f})."
            )
        # Invariant: Overall score cannot claim high confidence (>0.5) if regressions occurred
        if self.regression_score < 1.0 and self.overall > 0.7:
            raise UncalibratedConfidenceError(
                f"Overall confidence ({self.overall:.2f}) cannot exceed 0.7 when regressions exist (regression_score={self.regression_score:.2f})."
            )
        return self


class BugReport(BaseModel):
    """Representation of an identified bug in the target codebase."""

    id: UUID = Field(default_factory=uuid4)
    project_id: str
    title: str
    description: str
    file_path: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    suspected_root_cause: str
    severity: Severity
    status: BugStatus = BugStatus.DETECTED
    reproduction_evidence: Optional[ReproductionEvidence] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_line_range(self) -> BugReport:
        if self.line_end < self.line_start:
            raise ValueError(f"line_end ({self.line_end}) cannot be less than line_start ({self.line_start})")
        return self

    def record_reproduction_attempt(self, evidence: ReproductionEvidence) -> None:
        """Records reproduction attempt and updates bug confirmation status.

        Enforces Rule 2: Bug is 'confirmed' ONLY if the generated test fails on buggy code.
        """
        self.reproduction_evidence = evidence
        if evidence.confirms_bug:
            self.status = BugStatus.REPRODUCED_CONFIRMED
        else:
            self.status = BugStatus.UNCONFIRMED

    def assert_confirmed(self) -> None:
        """Asserts that this bug is confirmed before repair can begin."""
        if self.status != BugStatus.REPRODUCED_CONFIRMED:
            raise UnconfirmedBugError(
                f"Bug {self.id} cannot be repaired because it is not confirmed. "
                f"Current status: {self.status}. Reproduction test must fail first."
            )


# Patterns matching common test file directories and naming conventions
TEST_FILE_PATTERNS = [
    re.compile(r"(^|/)(test|tests|spec|specs|__tests__)/", re.IGNORECASE),
    re.compile(r"(_test|\.test|\.spec)\.(py|ts|tsx|js|jsx|go|rs|rb)$", re.IGNORECASE),
    re.compile(r"test_[^/]+\.(py|ts|js)$", re.IGNORECASE),
]


class Patch(BaseModel):
    """Proposed source code patch.

    Invariant (Rule 3): Change only what the root cause requires.
    NEVER modify existing tests.
    """

    id: UUID = Field(default_factory=uuid4)
    bug_id: UUID
    diff: str = Field(min_length=1, description="Unified diff of the patch")
    affected_files: List[str] = Field(min_length=1)
    rationale: str = Field(min_length=5, description="Explanation of why this patch resolves the root cause")
    ast_node_delta: int = Field(ge=0, description="Magnitude of AST modification")
    lines_added: int = Field(ge=0)
    lines_deleted: int = Field(ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("affected_files")
    @classmethod
    def validate_no_test_modifications(cls, files: List[str]) -> List[str]:
        """Enforces Rule 3: Never modify existing tests."""
        for f in files:
            for pattern in TEST_FILE_PATTERNS:
                if pattern.search(f):
                    raise TestModificationForbiddenError(
                        f"Patch attempts to modify existing test file '{f}'. "
                        "Rule 3 strictly prohibits modifying existing test files."
                    )
        return files


class VerificationEvidence(BaseModel):
    """Evidence proving that a patch fixes the bug without regressions.

    Invariant (Rule 2): A fix is verified ONLY if:
    1. The reproduction test passes after patch.
    2. Existing suite passes with 0 new failures.
    3. Run executed in an isolated sandbox.
    """

    patch_id: UUID
    reproduction_test_passed: bool
    existing_suite_passed: bool
    existing_tests_run_count: int = Field(ge=0)
    regression_count: int = Field(ge=0)
    execution_time_seconds: float = Field(ge=0.0)
    sandbox_isolated: bool = True
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_verified(self) -> bool:
        """Returns True if and only if both the reproduction test and regression suite passed."""
        return (
            self.reproduction_test_passed
            and self.existing_suite_passed
            and self.regression_count == 0
            and self.sandbox_isolated
        )

    def assert_verified(self) -> None:
        """Raises UnverifiedPatchError if invariants are not satisfied."""
        if not self.is_verified:
            reasons = []
            if not self.reproduction_test_passed:
                reasons.append("Reproduction test did not pass on patched code")
            if not self.existing_suite_passed:
                reasons.append("Existing test suite failed")
            if self.regression_count > 0:
                reasons.append(f"{self.regression_count} regressions introduced")
            if not self.sandbox_isolated:
                reasons.append("Test execution was not sandbox isolated")
            raise UnverifiedPatchError(f"Patch verification failed: {'; '.join(reasons)}")


class ApprovalDecision(BaseModel):
    """Cryptographically verifiable record of human approval or rejection."""

    bundle_id: UUID
    reviewer_id: str = Field(min_length=1)
    status: ApprovalStatus
    comment: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    signature_hash: str = ""

    @model_validator(mode="after")
    def compute_signature(self) -> ApprovalDecision:
        if not self.signature_hash:
            data = f"{self.bundle_id}:{self.reviewer_id}:{self.status.value}:{self.timestamp.isoformat()}"
            self.signature_hash = hashlib.sha256(data.encode("utf-8")).hexdigest()
        return self


class ReviewBundle(BaseModel):
    """The complete, transparent review bundle presented to human reviewers.

    Enforces Rule 1 (Trust): Every patch ships with:
    1. Root cause
    2. Diff
    3. Rationale
    4. Test evidence (reproduction + verification)
    5. Severity
    6. Calibrated confidence
    """

    id: UUID = Field(default_factory=uuid4)
    bug_report: BugReport
    patch: Patch
    root_cause: str = Field(min_length=10)
    rationale: str = Field(min_length=10)
    reproduction_evidence: ReproductionEvidence
    verification_evidence: VerificationEvidence
    severity: Severity
    confidence: ConfidenceScore
    approval_status: ApprovalStatus = ApprovalStatus.PENDING_APPROVAL
    approval_decision: Optional[ApprovalDecision] = None
    applied: bool = False
    applied_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_bundle_consistency(self) -> ReviewBundle:
        # Rule 2: Verification evidence must be valid for the review bundle
        if not self.verification_evidence.is_verified:
            raise UnverifiedPatchError(
                "Cannot create ReviewBundle with unverified patch evidence. "
                "Both reproduction test must pass and existing suite must have 0 regressions."
            )
        # Bug ID linkage check
        if self.patch.bug_id != self.bug_report.id:
            raise ValueError(
                f"Patch bug_id ({self.patch.bug_id}) does not match BugReport id ({self.bug_report.id})"
            )
        return self

    def approve(self, decision: ApprovalDecision) -> None:
        """Records explicit human approval for this patch."""
        if decision.bundle_id != self.id:
            raise ValueError(f"Decision bundle_id {decision.bundle_id} does not match ReviewBundle id {self.id}")
        if decision.status != ApprovalStatus.APPROVED:
            raise ValueError(f"Approval decision status must be APPROVED, got {decision.status}")
        self.approval_status = ApprovalStatus.APPROVED
        self.approval_decision = decision

    def reject(self, decision: ApprovalDecision) -> None:
        """Records explicit human rejection for this patch."""
        if decision.bundle_id != self.id:
            raise ValueError(f"Decision bundle_id {decision.bundle_id} does not match ReviewBundle id {self.id}")
        if decision.status != ApprovalStatus.REJECTED:
            raise ValueError(f"Rejection decision status must be REJECTED, got {decision.status}")
        self.approval_status = ApprovalStatus.REJECTED
        self.approval_decision = decision

    def apply_patch(self) -> None:
        """Applies the patch to the target codebase.

        Enforces Rule 1 (Trust): NO patch is ever applied without explicit human approval.
        """
        if self.approval_status != ApprovalStatus.APPROVED:
            raise UnauthorizedPatchApplicationError(
                f"Cannot apply patch {self.patch.id}: explicit human approval is required. "
                f"Current status: {self.approval_status}. (Rule 1 Non-negotiable)"
            )
        if not self.verification_evidence.is_verified:
            raise UnverifiedPatchError("Cannot apply patch: verification evidence is invalid.")
        self.applied = True
        self.applied_at = datetime.now(timezone.utc)


class AuditLogEntry(BaseModel):
    """Immutable audit record for every action in the AutoPatch lifecycle."""

    id: UUID = Field(default_factory=uuid4)
    event_type: str
    entity_id: str
    actor: str = "SYSTEM"
    details: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sha256: str = ""

    @model_validator(mode="after")
    def compute_sha(self) -> AuditLogEntry:
        if not self.sha256:
            content = f"{self.id}:{self.event_type}:{self.entity_id}:{self.actor}:{self.timestamp.isoformat()}"
            self.sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return self
