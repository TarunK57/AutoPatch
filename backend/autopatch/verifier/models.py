"""Data models for patch verification, sandboxed test execution, and ensemble evaluation."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    """Final outcome classification of candidate patch verification."""

    VERIFIED = "VERIFIED"
    PLAUSIBLE_BUT_UNVERIFIED = "PLAUSIBLE_BUT_UNVERIFIED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class SingleTestStatus(str, Enum):
    """Outcome status for an individual test case."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class SingleTestResult(BaseModel):
    """Detailed result for an individual executed test."""

    name: str
    status: SingleTestStatus
    duration_seconds: float = Field(ge=0.0, default=0.0)
    failure_message: Optional[str] = None


class StructuredTestExecutionResult(BaseModel):
    """Aggregated output from running tests inside an ephemeral sandbox."""

    command: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    test_results: List[SingleTestResult] = Field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    sandbox_network_disabled: bool = True
    sandbox_read_only: bool = True
    output_truncated: bool = False
    runner_type: str = "EPHEMERAL_LOCAL"

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0 and self.failed == 0 and self.errors == 0


class DifferentialCheckResult(BaseModel):
    """Results of calling unrelated public functions on baseline vs. patched code."""

    probed_functions: List[str] = Field(default_factory=list)
    baseline_outputs: Dict[str, Any] = Field(default_factory=dict)
    patched_outputs: Dict[str, Any] = Field(default_factory=dict)
    divergent: bool = False
    divergent_details: List[str] = Field(default_factory=list)


class OverfittingCheckResult(BaseModel):
    """Results of static and semantic overfitting inspection."""

    is_overfit: bool = False
    static_flags: List[str] = Field(default_factory=list)
    llm_review_notes: Optional[str] = None
    confidence_penalty: float = Field(ge=0.0, le=1.0, default=0.0)


class PatchVerificationResult(BaseModel):
    """Complete verification dossier for a candidate patch."""

    patch_id: str
    status: VerificationStatus
    reasons: List[str] = Field(default_factory=list)
    brt_failed_on_baseline: bool = False
    brt_passed_on_patch: bool = False
    baseline_suite_passed: bool = False
    patch_suite_passed: bool = False
    regressions: List[str] = Field(default_factory=list)
    build_lint_passed: bool = False
    differential_check: DifferentialCheckResult = Field(default_factory=DifferentialCheckResult)
    flakiness_stability_score: float = Field(ge=0.0, le=1.0, default=1.0)
    ensemble_pass_rate: float = Field(ge=0.0, le=100.0, default=0.0)
    diff_size: int = Field(ge=0, default=0)
    overfitting: OverfittingCheckResult = Field(default_factory=OverfittingCheckResult)
    rank: int = 1
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EnsembleEvaluation(BaseModel):
    """Ensemble pass rate evaluation and ranking across candidate patches."""

    candidate_rankings: List[PatchVerificationResult] = Field(default_factory=list)
    selection_mode: str = "TOP_K"  # "TOP_K" or "THRESHOLD"
    top_k: int = 1
    selected_patch: Optional[PatchVerificationResult] = None
    evaluation_notes: str = ""
