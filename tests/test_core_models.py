"""Unit tests for AutoPatch core domain models, enums, and safety invariants."""

from datetime import datetime, timezone
from uuid import uuid4
import pytest
from pydantic import ValidationError

from autopatch.core.exceptions import (
    TestModificationForbiddenError,
    UnauthorizedPatchApplicationError,
    UnconfirmedBugError,
    UnverifiedPatchError,
    UncalibratedConfidenceError,
)
from autopatch.core.models import (
    ApprovalDecision,
    ApprovalStatus,
    BugReport,
    BugStatus,
    ConfidenceScore,
    Patch,
    ReproductionEvidence,
    ReviewBundle,
    Severity,
    VerificationEvidence,
)


def test_severity_ordering():
    """Verify that severity follows strict priority ordering."""
    assert Severity.LOW < Severity.MEDIUM < Severity.HIGH < Severity.CRITICAL
    assert Severity.CRITICAL > Severity.HIGH
    assert Severity.MEDIUM <= Severity.MEDIUM
    assert Severity.HIGH >= Severity.LOW
    assert Severity.LOW.rank == 1
    assert Severity.CRITICAL.rank == 4


def test_bug_report_line_validation():
    """Verify line start/end validation rules."""
    with pytest.raises(ValidationError):
        BugReport(
            project_id="proj_1",
            title="Off by one",
            description="Array indexing error",
            file_path="src/index.py",
            line_start=15,
            line_end=10,  # Invalid: end < start
            suspected_root_cause="Bad boundary condition",
            severity=Severity.HIGH,
        )


def test_reproduce_before_repair_rule2_confirmed():
    """Enforces Rule 2: Bug confirmed ONLY if reproduction test fails on buggy code."""
    bug = BugReport(
        project_id="proj_1",
        title="Null pointer in auth handler",
        description="Missing check on token claims",
        file_path="src/auth.py",
        line_start=20,
        line_end=25,
        suspected_root_cause="Claims dictionary accessed without key check",
        severity=Severity.HIGH,
    )

    # Simulated reproduction test that reproduces the bug (fails with exit code 1)
    repro_failure = ReproductionEvidence(
        test_code="def test_auth_null(): assert authenticate(None) is not None",
        test_file_path="tests/repro_test.py",
        execution_log="KeyError: 'user_id'",
        exit_code=1,
        passed=False,
        error_message="KeyError: 'user_id'",
    )

    assert repro_failure.confirms_bug is True
    bug.record_reproduction_attempt(repro_failure)
    assert bug.status == BugStatus.REPRODUCED_CONFIRMED

    # Calling assert_confirmed should not raise
    bug.assert_confirmed()


def test_reproduce_before_repair_rule2_unconfirmed():
    """Enforces Rule 2: If reproduction test passes, bug is UNCONFIRMED and cannot proceed to repair."""
    bug = BugReport(
        project_id="proj_1",
        title="Phantom bug",
        description="User claims division by zero occurs",
        file_path="src/calc.py",
        line_start=10,
        line_end=12,
        suspected_root_cause="Zero denominator",
        severity=Severity.MEDIUM,
    )

    # Simulated test that fails to reproduce the bug (passes with exit code 0)
    repro_passed = ReproductionEvidence(
        test_code="def test_calc(): assert calc(10, 2) == 5",
        test_file_path="tests/repro_test.py",
        execution_log="1 passed in 0.01s",
        exit_code=0,
        passed=True,
    )

    assert repro_passed.confirms_bug is False
    bug.record_reproduction_attempt(repro_passed)
    assert bug.status == BugStatus.UNCONFIRMED

    # Attempting to assert confirmed must raise UnconfirmedBugError
    with pytest.raises(UnconfirmedBugError) as exc_info:
        bug.assert_confirmed()
    assert "cannot be repaired because it is not confirmed" in str(exc_info.value)


def test_minimal_diffs_rule3_rejects_test_modification():
    """Enforces Rule 3: Never modify existing tests."""
    bug_id = uuid4()

    # Valid patch touching application code
    valid_patch = Patch(
        bug_id=bug_id,
        diff="--- a/src/auth.py\n+++ b/src/auth.py\n@@ -20,1 +20,1 @@\n- x = 1\n+ x = 2",
        affected_files=["src/auth.py"],
        rationale="Fix off-by-one boundary check in token parser",
        ast_node_delta=2,
        lines_added=1,
        lines_deleted=1,
    )
    assert valid_patch.affected_files == ["src/auth.py"]

    # Prohibited patches attempting to modify test files
    forbidden_targets = [
        ["tests/test_auth.py"],
        ["src/auth.test.ts"],
        ["spec/models/user_spec.rb"],
        ["__tests__/login.test.js"],
        ["src/handlers/test_worker.py"],
    ]

    for forbidden_files in forbidden_targets:
        with pytest.raises(TestModificationForbiddenError):
            Patch(
                bug_id=bug_id,
                diff="--- a/test\n+++ b/test",
                affected_files=forbidden_files,
                rationale="Attempting to adjust tests to match new behavior",
                ast_node_delta=1,
                lines_added=1,
                lines_deleted=0,
            )


def test_verification_evidence_invariants():
    """Enforces Rule 2: Verified ONLY if repro test passes AND existing suite has 0 regressions."""
    patch_id = uuid4()

    # Case 1: Fully verified
    evidence_verified = VerificationEvidence(
        patch_id=patch_id,
        reproduction_test_passed=True,
        existing_suite_passed=True,
        existing_tests_run_count=150,
        regression_count=0,
        execution_time_seconds=2.45,
        sandbox_isolated=True,
    )
    assert evidence_verified.is_verified is True
    evidence_verified.assert_verified()  # Should not raise

    # Case 2: Repro test still fails
    evidence_repro_failed = VerificationEvidence(
        patch_id=patch_id,
        reproduction_test_passed=False,
        existing_suite_passed=True,
        existing_tests_run_count=150,
        regression_count=0,
        execution_time_seconds=1.2,
        sandbox_isolated=True,
    )
    assert evidence_repro_failed.is_verified is False
    with pytest.raises(UnverifiedPatchError) as exc:
        evidence_repro_failed.assert_verified()
    assert "Reproduction test did not pass" in str(exc.value)

    # Case 3: Regression in existing suite
    evidence_regression = VerificationEvidence(
        patch_id=patch_id,
        reproduction_test_passed=True,
        existing_suite_passed=False,
        existing_tests_run_count=150,
        regression_count=2,
        execution_time_seconds=3.1,
        sandbox_isolated=True,
    )
    assert evidence_regression.is_verified is False
    with pytest.raises(UnverifiedPatchError) as exc:
        evidence_regression.assert_verified()
    assert "2 regressions introduced" in str(exc.value)

    # Case 4: Not sandbox isolated
    evidence_unsandboxed = VerificationEvidence(
        patch_id=patch_id,
        reproduction_test_passed=True,
        existing_suite_passed=True,
        existing_tests_run_count=150,
        regression_count=0,
        execution_time_seconds=2.0,
        sandbox_isolated=False,
    )
    assert evidence_unsandboxed.is_verified is False
    with pytest.raises(UnverifiedPatchError) as exc:
        evidence_unsandboxed.assert_verified()
    assert "not sandbox isolated" in str(exc.value)


def test_honest_uncertainty_rule5_confidence_calibration():
    """Enforces Rule 5: Confidence must be calibrated and explained. Never claim unrun verification."""
    # Invalid: High overall confidence without reproduction evidence
    with pytest.raises(UncalibratedConfidenceError):
        ConfidenceScore(
            reproduction_score=0.2,  # Low repro
            regression_score=1.0,
            minimal_diff_score=0.9,
            llm_reasoning_score=0.9,
            overall=0.85,  # Unjustified high score
            calibration_notes="Reproduction was flaky but we are confident in the LLM.",
        )

    # Invalid: High overall confidence despite regression
    with pytest.raises(UncalibratedConfidenceError):
        ConfidenceScore(
            reproduction_score=1.0,
            regression_score=0.5,  # Regressions exist
            minimal_diff_score=0.9,
            llm_reasoning_score=0.9,
            overall=0.80,  # Unjustified
            calibration_notes="A few tests broke but this patch is needed.",
        )

    # Valid calibrated score with honest explanation
    valid_score = ConfidenceScore(
        reproduction_score=1.0,
        regression_score=1.0,
        minimal_diff_score=0.95,
        llm_reasoning_score=0.90,
        overall=0.94,
        calibration_notes="Deterministic reproduction test failed on baseline and passed after patch with 0 regressions across 124 existing tests.",
    )
    assert valid_score.overall == 0.94


def test_trust_rule1_human_approval_required():
    """Enforces Rule 1: No patch is ever applied without explicit human approval."""
    bug = BugReport(
        project_id="proj_alpha",
        title="Division by zero in billing calculations",
        description="Quantity of zero triggers uncaught ZeroDivisionError",
        file_path="src/billing.py",
        line_start=45,
        line_end=48,
        suspected_root_cause="Missing non-zero check on billing divisor",
        severity=Severity.HIGH,
    )

    repro_evidence = ReproductionEvidence(
        test_code="def test_zero_qty(): calculate_total(100, 0)",
        test_file_path="tests/repro_billing.py",
        execution_log="ZeroDivisionError: division by zero",
        exit_code=1,
        passed=False,
    )
    bug.record_reproduction_attempt(repro_evidence)

    patch = Patch(
        bug_id=bug.id,
        diff="--- a/src/billing.py\n+++ b/src/billing.py\n@@ -45,1 +45,2 @@\n- return total / qty\n+ return total / qty if qty > 0 else 0",
        affected_files=["src/billing.py"],
        rationale="Guard against zero denominator by returning 0 when quantity is zero",
        ast_node_delta=3,
        lines_added=1,
        lines_deleted=1,
    )

    verification = VerificationEvidence(
        patch_id=patch.id,
        reproduction_test_passed=True,
        existing_suite_passed=True,
        existing_tests_run_count=88,
        regression_count=0,
        execution_time_seconds=1.42,
        sandbox_isolated=True,
    )

    confidence = ConfidenceScore(
        reproduction_score=1.0,
        regression_score=1.0,
        minimal_diff_score=0.98,
        llm_reasoning_score=0.95,
        overall=0.97,
        calibration_notes="Reproduction confirmed, 88 tests verified clean, single line guard added.",
    )

    bundle = ReviewBundle(
        bug_report=bug,
        patch=patch,
        root_cause="billing.py divides total by qty without validating that qty is strictly positive",
        rationale="Adding a ternary guard resolves the ZeroDivisionError while preserving calculation logic",
        reproduction_evidence=repro_evidence,
        verification_evidence=verification,
        severity=bug.severity,
        confidence=confidence,
    )

    # Initial state must be PENDING_APPROVAL and unapplied
    assert bundle.approval_status == ApprovalStatus.PENDING_APPROVAL
    assert bundle.applied is False

    # Attempting to apply without human approval MUST raise UnauthorizedPatchApplicationError
    with pytest.raises(UnauthorizedPatchApplicationError) as exc_info:
        bundle.apply_patch()
    assert "explicit human approval is required" in str(exc_info.value)
    assert bundle.applied is False

    # Simulate explicit human approval
    decision = ApprovalDecision(
        bundle_id=bundle.id,
        reviewer_id="human_reviewer_42",
        status=ApprovalStatus.APPROVED,
        comment="Diff is minimal and evidence looks solid.",
    )
    bundle.approve(decision)
    assert bundle.approval_status == ApprovalStatus.APPROVED
    assert bundle.approval_decision is not None
    assert bundle.approval_decision.signature_hash != ""

    # Now apply_patch must succeed
    bundle.apply_patch()
    assert bundle.applied is True
    assert bundle.applied_at is not None


def test_trust_rule1_rejection_prevents_application():
    """Verify that human rejection permanently prevents patch application."""
    bug = BugReport(
        project_id="proj_beta",
        title="Memory leak in socket handler",
        description="Sockets not closed",
        file_path="src/net.py",
        line_start=12,
        line_end=15,
        suspected_root_cause="Missing socket close in finally block",
        severity=Severity.MEDIUM,
    )
    repro = ReproductionEvidence(
        test_code="def test_socket(): pass",
        test_file_path="tests/repro.py",
        execution_log="Failure",
        exit_code=1,
        passed=False,
    )
    bug.record_reproduction_attempt(repro)

    patch = Patch(
        bug_id=bug.id,
        diff="--- a/src/net.py\n+++ b/src/net.py\n@@ -12,1 +12,2 @@\n- pass\n+ sock.close()",
        affected_files=["src/net.py"],
        rationale="Close socket explicitly",
        ast_node_delta=2,
        lines_added=1,
        lines_deleted=1,
    )
    verification = VerificationEvidence(
        patch_id=patch.id,
        reproduction_test_passed=True,
        existing_suite_passed=True,
        existing_tests_run_count=10,
        regression_count=0,
        execution_time_seconds=0.5,
        sandbox_isolated=True,
    )
    confidence = ConfidenceScore(
        reproduction_score=1.0,
        regression_score=1.0,
        minimal_diff_score=1.0,
        llm_reasoning_score=0.9,
        overall=0.95,
        calibration_notes="Socket closed cleanly in reproduction tests.",
    )

    bundle = ReviewBundle(
        bug_report=bug,
        patch=patch,
        root_cause="Unclosed socket handles",
        rationale="Call sock.close()",
        reproduction_evidence=repro,
        verification_evidence=verification,
        severity=bug.severity,
        confidence=confidence,
    )

    rejection = ApprovalDecision(
        bundle_id=bundle.id,
        reviewer_id="lead_eng",
        status=ApprovalStatus.REJECTED,
        comment="Prefer using context manager 'with socket' instead of manual close",
    )
    bundle.reject(rejection)
    assert bundle.approval_status == ApprovalStatus.REJECTED

    with pytest.raises(UnauthorizedPatchApplicationError):
        bundle.apply_patch()
    assert bundle.applied is False
