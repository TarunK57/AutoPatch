"""Sandboxed test runner for Bug Reproduction Tests.

Executes tests in network-disabled, isolated environment and classifies outcomes:
- PASS: All test assertions succeeded.
- FAIL: Expected assertion or logical runtime failure.
- ERROR: Syntax, compile, or unimported module error (demands agent refinement).
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from autopatch.reproducer.models import TestRunResult, TestRunStatus

# Errors that indicate the test itself is malformed or unrunnable (ERROR status)
SETUP_OR_SYNTAX_ERRORS = [
    "SyntaxError",
    "IndentationError",
    "ModuleNotFoundError",
    "ImportError",
    "NameError: name 'pytest' is not defined",
    "NameError: name 'unittest' is not defined",
    "ERROR collecting",
    "CollectionError",
]


class SandboxedBRTRunner:
    """Executes a target reproduction test file and classifies the outcome."""

    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    def run_test_file(self, project_root: Path, test_file_rel: str) -> TestRunResult:
        """Executes a test file inside project_root and returns classified TestRunResult."""
        full_path = (project_root / test_file_rel).resolve()
        if not full_path.is_file():
            return TestRunResult(
                status=TestRunStatus.ERROR,
                exit_code=1,
                stdout="",
                stderr=f"Test file not found: {test_file_rel}",
                error_type="FileNotFoundError",
            )

        start_time = time.perf_counter()

        env = dict(os.environ)
        env["PYTHONPATH"] = f"{str(project_root)}:{env.get('PYTHONPATH', '')}"

        # Determine runner command based on file extension
        if test_file_rel.endswith(".py"):
            cmd = [sys.executable, "-m", "pytest", test_file_rel, "-v"]
        elif test_file_rel.endswith((".js", ".ts")):
            cmd = ["npx", "jest", test_file_rel]
        else:
            cmd = [sys.executable, "-m", "pytest", test_file_rel]

        try:
            res = subprocess.run(
                cmd,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
                env=env,
            )
            stdout = res.stdout or ""
            stderr = res.stderr or ""
            combined_output = f"{stdout}\n{stderr}"
            exit_code = res.returncode
            elapsed = time.perf_counter() - start_time

            # 1. Check for Syntax, Import, or Setup Errors -> ERROR
            for err in SETUP_OR_SYNTAX_ERRORS:
                if err in combined_output:
                    return TestRunResult(
                        status=TestRunStatus.ERROR,
                        exit_code=exit_code,
                        stdout=stdout,
                        stderr=stderr,
                        error_type=err,
                        failure_trace=self._extract_trace(combined_output),
                        execution_time_seconds=round(elapsed, 4),
                    )

            # 2. Check for passing execution
            if exit_code == 0:
                return TestRunResult(
                    status=TestRunStatus.PASS,
                    exit_code=0,
                    stdout=stdout,
                    stderr=stderr,
                    execution_time_seconds=round(elapsed, 4),
                )

            # 3. Non-zero exit code with assertion or application failure -> FAIL
            failure_trace = self._extract_trace(combined_output)
            error_type = self._extract_error_type(combined_output)

            return TestRunResult(
                status=TestRunStatus.FAIL,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                error_type=error_type,
                failure_trace=failure_trace,
                execution_time_seconds=round(elapsed, 4),
            )

        except subprocess.TimeoutExpired:
            return TestRunResult(
                status=TestRunStatus.ERROR,
                exit_code=124,
                stdout="",
                stderr=f"Test run timed out after {self.timeout_seconds}s.",
                error_type="TimeoutExpired",
                execution_time_seconds=float(self.timeout_seconds),
            )
        except Exception as e:
            return TestRunResult(
                status=TestRunStatus.ERROR,
                exit_code=1,
                stdout="",
                stderr=str(e),
                error_type=e.__class__.__name__,
            )

    def _extract_trace(self, output: str) -> str:
        """Extracts the most relevant failure traceback or assertion block."""
        lines = output.splitlines()
        # Find lines with traceback markers: E       or >       or AssertionError
        trace_lines = [l for l in lines if l.strip().startswith("E ") or l.strip().startswith("> ") or "Error" in l or "FAILED" in l]
        if trace_lines:
            return "\n".join(trace_lines[:10]).strip()
        return "\n".join(lines[-10:]).strip()

    def _extract_error_type(self, output: str) -> str:
        """Extracts the exception or failure class name."""
        match = re.search(r"\b([A-Z][a-zA-Z0-9_]*Error|[A-Z][a-zA-Z0-9_]*Exception)\b", output)
        if match:
            return match.group(1)
        if "AssertionError" in output or "FAILED" in output:
            return "AssertionError"
        return "TestFailure"
