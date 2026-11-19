"""Unit tests verifying differential checking on untouched functions and flakiness stability scoring.

Acceptance Criteria:
- Differential checking confirms behavioral invariance on untouched public functions.
- Flakiness testing calculates stability score across repeated trials (N_consistent / N_trials).
- Test flakiness triggers NEEDS_REVIEW status.
"""

import tempfile
from pathlib import Path
from uuid import uuid4

from autopatch.patcher.models import CandidatePatch
from autopatch.verifier.differential import DifferentialChecker
from autopatch.verifier.engine import VerifierEngine
from autopatch.verifier.models import (
    SingleTestResult,
    SingleTestStatus,
    StructuredTestExecutionResult,
    VerificationStatus,
)
from autopatch.verifier.sandbox import EphemeralSandbox


def test_differential_checker_invariance_on_untouched_functions():
    with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
        base_dir = Path(td1)
        patch_dir = Path(td2)

        # Create untouched utility module in both snapshots
        for d in (base_dir, patch_dir):
            utils_dir = d / "pkg"
            utils_dir.mkdir(parents=True, exist_ok=True)
            (utils_dir / "__init__.py").write_text("")
            (utils_dir / "utils.py").write_text(
                """def compute_multiplier(x):
    return x * 2

def greet(name):
    return f"hello_{name}"
"""
            )

        checker = DifferentialChecker()
        res = checker.run_differential_check(
            baseline_snapshot=base_dir,
            patched_snapshot=patch_dir,
            affected_files=["pkg/core.py"],  # core.py is modified, utils.py is untouched
        )

        assert res.divergent is False
        assert len(res.probed_functions) >= 2
        assert any("compute_multiplier" in f for f in res.probed_functions)
        assert len(res.divergent_details) == 0


def test_differential_checker_detects_collateral_behavior_drift():
    with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
        base_dir = Path(td1)
        patch_dir = Path(td2)

        # Baseline version of untouched module
        base_pkg = base_dir / "pkg"
        base_pkg.mkdir(parents=True, exist_ok=True)
        (base_pkg / "__init__.py").write_text("")
        (base_pkg / "helpers.py").write_text("def answer(x): return 42\n")

        # Patched version where untouched module unexpectedly behaves differently
        patch_pkg = patch_dir / "pkg"
        patch_pkg.mkdir(parents=True, exist_ok=True)
        (patch_pkg / "__init__.py").write_text("")
        (patch_pkg / "helpers.py").write_text("def answer(x): return 999\n")

        checker = DifferentialChecker()
        res = checker.run_differential_check(
            baseline_snapshot=base_dir,
            patched_snapshot=patch_dir,
            affected_files=["pkg/other.py"],
        )

        assert res.divergent is True
        assert any("answer" in d for d in res.divergent_details)


def test_flakiness_stability_score_and_needs_review():
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        src = proj / "src"
        src.mkdir()
        (src / "service.py").write_text("def work(): return 1\n")

        test_file = proj / "test_flaky.py"
        test_file.write_text("def test_service(): assert True\n")

        patch = CandidatePatch(
            id=uuid4(),
            file="src/service.py",
            original_snippet="def work(): return 1",
            patched_snippet="def work(): return 1 # ok",
            rationale="Harmless patch",
            lines_added=1,
            lines_deleted=1,
        )

        class IntermittentFlakySandbox(EphemeralSandbox):
            def __init__(self):
                super().__init__()
                self.flaky_call_count = 0

            def run_tests(self, project_snapshot, command):
                res = super().run_tests(project_snapshot, command)
                # Intermittently fail the 2nd flakiness trial (which is call #6)
                if "test_flaky.py" in command:
                    self.flaky_call_count += 1
                    if self.flaky_call_count == 6:  # 2nd flakiness trial
                        return StructuredTestExecutionResult(
                            command=command,
                            total_tests=1,
                            passed=0,
                            failed=1,
                            exit_code=1,
                            test_results=[
                                SingleTestResult(
                                    name="test_flaky.py::test_service",
                                    status=SingleTestStatus.FAILED,
                                    failure_message="Random socket or thread timeout",
                                )
                            ],
                        )
                return res

        engine = VerifierEngine(sandbox=IntermittentFlakySandbox(), flakiness_runs=3)
        evaluation = engine.verify_candidate_patches(
            project_root=proj,
            candidate_patches=[patch],
            brt_test_paths=["test_flaky.py"],
            existing_test_command="pytest test_flaky.py",
        )

        assert len(evaluation.candidate_rankings) == 1
        res = evaluation.candidate_rankings[0]

        # 2 out of 3 trials matched -> stability score is 0.67 < 0.8
        assert res.flakiness_stability_score < 1.0
        assert res.status == VerificationStatus.NEEDS_REVIEW
        assert any("flakiness" in reason.lower() for reason in res.reasons)
