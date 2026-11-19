"""Unit tests verifying that patches causing regressions are strictly blocked (Rule 2).

Acceptance Criteria:
- A patch that fixes the bug but breaks an existing test is blocked (status=FAILED, regression listed).
- A clean patch that fixes the bug with 0 regressions is VERIFIED.
"""

import tempfile
from pathlib import Path
from uuid import uuid4

from autopatch.patcher.models import CandidatePatch
from autopatch.verifier.engine import VerifierEngine
from autopatch.verifier.models import VerificationStatus


def test_patch_introducing_regression_is_strictly_blocked():
    """Rule 2: Verification invariant - 0 new test failures allowed."""
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        src_dir = proj / "src"
        src_dir.mkdir()
        test_dir = proj / "tests"
        test_dir.mkdir()

        # Target source file with division bug on zero
        calc_file = src_dir / "calc.py"
        calc_file.write_text(
            """def add(a, b):
    return a + b

def divide(a, b):
    return a / b
"""
        )

        # Existing test suite testing normal addition and division
        existing_test = test_dir / "test_existing.py"
        existing_test.write_text(
            """from src.calc import add, divide

def test_add():
    assert add(2, 3) == 5

def test_divide_normal():
    assert divide(10, 2) == 5
"""
        )

        # BRT reproduction test expecting 0 on divide by zero
        brt_test_code = """from src.calc import divide

def test_divide_zero_repro():
    assert divide(10, 0) == 0
"""

        # Patch 1: Regressive patch - handles 0, but breaks normal division by returning a - b!
        regressive_patch = CandidatePatch(
            id=uuid4(),
            file="src/calc.py",
            original_snippet="def divide(a, b):\n    return a / b",
            patched_snippet="def divide(a, b):\n    if b == 0:\n        return 0\n    return a - b",
            rationale="Fixes zero division but accidentally broke normal division logic",
            lines_added=4,
            lines_deleted=2,
        )

        engine = VerifierEngine(flakiness_runs=1)
        evaluation = engine.verify_candidate_patches(
            project_root=proj,
            candidate_patches=[regressive_patch],
            brt_test_paths=["tests/test_repro.py"],
            brt_contents={"tests/test_repro.py": brt_test_code},
            existing_test_command="pytest tests/test_existing.py",
        )

        assert len(evaluation.candidate_rankings) == 1
        result = evaluation.candidate_rankings[0]

        # Patch MUST be blocked due to regression
        assert result.status == VerificationStatus.FAILED
        assert result.patch_suite_passed is False
        assert len(result.regressions) > 0
        assert any("test_divide_normal" in r for r in result.regressions)
        assert any("Regression detected" in reason for reason in result.reasons)


def test_clean_patch_with_zero_regressions_is_verified():
    """Rule 2: Bug confirmed by failing on baseline, passing on patch, and 0 regressions."""
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        src_dir = proj / "src"
        src_dir.mkdir()
        test_dir = proj / "tests"
        test_dir.mkdir()

        calc_file = src_dir / "calc.py"
        calc_file.write_text(
            """def add(a, b):
    return a + b

def divide(a, b):
    return a / b
"""
        )

        existing_test = test_dir / "test_existing.py"
        existing_test.write_text(
            """from src.calc import add, divide

def test_add():
    assert add(2, 3) == 5

def test_divide_normal():
    assert divide(10, 2) == 5
"""
        )

        brt_test_code = """from src.calc import divide

def test_divide_zero_repro():
    assert divide(10, 0) == 0
"""

        # Clean minimal patch
        clean_patch = CandidatePatch(
            id=uuid4(),
            file="src/calc.py",
            original_snippet="def divide(a, b):\n    return a / b",
            patched_snippet="def divide(a, b):\n    if b == 0:\n        return 0\n    return a / b",
            rationale="Adds zero division guard returning 0 when divisor is zero",
            lines_added=4,
            lines_deleted=2,
        )

        engine = VerifierEngine(flakiness_runs=1)
        evaluation = engine.verify_candidate_patches(
            project_root=proj,
            candidate_patches=[clean_patch],
            brt_test_paths=["tests/test_repro.py"],
            brt_contents={"tests/test_repro.py": brt_test_code},
            existing_test_command="pytest tests/test_existing.py",
        )

        assert len(evaluation.candidate_rankings) == 1
        result = evaluation.candidate_rankings[0]

        # Validated verification outcome
        assert result.status == VerificationStatus.VERIFIED
        assert result.brt_failed_on_baseline is True
        assert result.brt_passed_on_patch is True
        assert result.patch_suite_passed is True
        assert len(result.regressions) == 0
        assert evaluation.selected_patch is not None
        assert evaluation.selected_patch.patch_id == str(clean_patch.id)
