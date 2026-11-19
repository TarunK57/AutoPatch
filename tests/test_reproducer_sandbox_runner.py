"""Unit tests for sandboxed reproduction test runner and outcome classification."""

from pathlib import Path
import pytest
from autopatch.reproducer.models import TestRunStatus
from autopatch.reproducer.sandbox_runner import SandboxedBRTRunner


def test_runner_classifies_pass(tmp_path: Path):
    """Verify passing test run is classified as PASS."""
    (tmp_path / "tests").mkdir()
    test_file = tmp_path / "tests/test_pass.py"
    test_file.write_text("def test_ok(): assert 1 + 1 == 2\n")

    runner = SandboxedBRTRunner()
    result = runner.run_test_file(tmp_path, "tests/test_pass.py")

    assert result.status == TestRunStatus.PASS
    assert result.exit_code == 0


def test_runner_classifies_fail_with_trace(tmp_path: Path):
    """Verify expected failure on buggy code is classified as FAIL with failure trace."""
    (tmp_path / "tests").mkdir()
    test_file = tmp_path / "tests/test_fail.py"
    test_file.write_text("def test_zero_div(): 1 / 0\n")

    runner = SandboxedBRTRunner()
    result = runner.run_test_file(tmp_path, "tests/test_fail.py")

    assert result.status == TestRunStatus.FAIL
    assert result.exit_code != 0
    assert result.error_type == "ZeroDivisionError"
    assert "division by zero" in result.failure_trace


def test_runner_classifies_error_on_syntax_or_import_issue(tmp_path: Path):
    """Verify compile/syntax/import errors are classified as ERROR to demand agent refinement."""
    (tmp_path / "tests").mkdir()

    # Syntax error file
    bad_syntax = tmp_path / "tests/test_bad_syntax.py"
    bad_syntax.write_text("def test_broken(:\n    assert True\n")

    runner = SandboxedBRTRunner()
    res_syntax = runner.run_test_file(tmp_path, "tests/test_bad_syntax.py")
    assert res_syntax.status == TestRunStatus.ERROR
    assert "SyntaxError" in res_syntax.error_type

    # Missing module import
    missing_import = tmp_path / "tests/test_bad_import.py"
    missing_import.write_text("import non_existent_super_module_xyz\ndef test_fn(): pass\n")
    res_import = runner.run_test_file(tmp_path, "tests/test_bad_import.py")
    assert res_import.status == TestRunStatus.ERROR
    assert "ModuleNotFoundError" in res_import.error_type
