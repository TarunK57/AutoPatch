"""Test-failure detector that runs the project's test suite in sandbox and parses failures."""

import re
import subprocess
from pathlib import Path
from typing import List, Optional

from autopatch.detection.base import BaseDetector, CancellationToken
from autopatch.detection.models import Finding, FindingCategory
from autopatch.ingestion.project_map import ProjectMapper
from autopatch.intelligence.models import FileASTIndex


class TestFailureDetector(BaseDetector):
    """Executes existing test suite in sandboxed environment and turns failures into Findings."""

    __test__ = False

    def __init__(self, mapper: Optional[ProjectMapper] = None):
        self.mapper = mapper or ProjectMapper()

    @property
    def name(self) -> str:
        return "TEST_FAILURE"

    def detect(
        self,
        project_root: Path,
        file_indices: List[FileASTIndex],
        cancel_token: Optional[CancellationToken] = None,
    ) -> List[Finding]:
        findings: List[Finding] = []

        if cancel_token:
            cancel_token.check_cancelled()

        pmap = self.mapper.build_project_map(project_root)
        if not pmap.test_command:
            return findings

        # Run test command inside sandbox / project root
        try:
            cmd = pmap.test_command.split()
            result = subprocess.run(
                cmd,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
        except Exception:
            return findings

        # If tests passed with exit code 0, no findings
        if result.returncode == 0:
            return findings

        # Parse test failure output
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        findings.extend(self.parse_test_output(output, project_root))
        return findings

    def parse_test_output(self, output: str, project_root: Path) -> List[Finding]:
        findings: List[Finding] = []

        # 1. Match Pytest style failures:
        # FAILED tests/test_calc.py::test_div_zero - ZeroDivisionError: division by zero
        # _________________________ test_div_zero _________________________
        # >       return a / b
        # E       ZeroDivisionError: division by zero
        # src/calc.py:12: ZeroDivisionError
        traceback_pattern = re.compile(
            r"""(?mx)
            (?:^_{3,}\s+([a-zA-Z0-9_]+)\s+_{3,}$) # Test header
            ([\s\S]+?)                           # Body
            (?:^(?:E\s+([a-zA-Z0-9_]+Error:[^\n]+)|[a-zA-Z0-9_]+Error:[^\n]+)) # Error line
            """
        )

        file_line_pattern = re.compile(r"([a-zA-Z0-9_./\\-]+\.py):(\d+):")

        for match in traceback_pattern.finditer(output):
            test_name = match.group(1)
            body = match.group(2)
            err_msg = match.group(3) or "Test assertion failure"

            # Look for the last source file reference (typically the error site)
            locations = file_line_pattern.findall(body)
            target_file = None
            target_line = 1

            for fpath, lnum in reversed(locations):
                # Prefer application source files over test files if present
                if not any(x in fpath for x in ["test_", "_test", "site-packages"]):
                    target_file = fpath
                    target_line = int(lnum)
                    break

            if not target_file and locations:
                target_file, target_line_str = locations[-1]
                target_line = int(target_line_str)

            if target_file:
                # Clean up relative path
                try:
                    rel_target = str(Path(target_file).relative_to(project_root))
                except Exception:
                    rel_target = target_file

                # Extract concise evidence block from body
                evidence_lines = [l for l in body.splitlines() if l.strip().startswith(">") or l.strip().startswith("E")]
                evidence = "\n".join(evidence_lines).strip() or err_msg

                findings.append(
                    Finding(
                        file=rel_target,
                        line_start=target_line,
                        line_end=target_line,
                        symbol=test_name,
                        category=FindingCategory.TEST_FAILURE,
                        evidence=evidence,
                        detector=self.name,
                        raw_confidence=0.99,
                        description=f"Automated test '{test_name}' failed: {err_msg}",
                        metadata={"test_name": test_name, "raw_error": err_msg},
                    )
                )

        return findings
