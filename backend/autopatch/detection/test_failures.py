"""Test-failure detector that runs the project's test suite in sandbox and parses failures."""

import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from autopatch.detection.base import BaseDetector, CancellationToken
from autopatch.detection.models import Finding, FindingCategory
from autopatch.ingestion.project_map import ProjectMapper
from autopatch.intelligence.models import FileASTIndex


def resolve_test_to_source(project_root: Path, test_file_rel: str, test_func_name: str) -> Tuple[Optional[str], int, Optional[str]]:
    """Inspects test file AST to map a failing test back to the production source file and symbol."""
    full_path = project_root / test_file_rel
    if not full_path.is_file():
        return None, 1, None

    try:
        tree = ast.parse(full_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None, 1, None

    # Track imports: symbol_name -> (module_path, original_name)
    imports = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imports[alias.asname or alias.name] = (node.module, alias.name)

    # Find test function definition
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == test_func_name:
            for call in ast.walk(node):
                if isinstance(call, ast.Call):
                    func_id = None
                    if isinstance(call.func, ast.Name):
                        func_id = call.func.id
                    elif isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
                        func_id = call.func.value.id

                    if func_id and func_id in imports:
                        mod_name, orig_sym = imports[func_id]
                        rel_py = mod_name.replace(".", "/") + ".py"
                        candidates = [
                            project_root / rel_py,
                            project_root / "src" / (mod_name.replace("src.", "").replace(".", "/") + ".py"),
                        ]
                        for cand in candidates:
                            if cand.is_file():
                                src_rel = str(cand.relative_to(project_root))
                                # Locate line in source file
                                sym_line = 1
                                try:
                                    src_tree = ast.parse(cand.read_text(encoding="utf-8", errors="replace"))
                                    for s_node in ast.walk(src_tree):
                                        if isinstance(s_node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                                            if s_node.name == orig_sym:
                                                sym_line = s_node.lineno
                                                break
                                except Exception:
                                    pass
                                return src_rel, sym_line, orig_sym

    return None, 1, None


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
            if cmd and cmd[0] == "pytest":
                cmd = [sys.executable, "-m", "pytest", "-v", "-o", 'addopts=""'] + cmd[1:]
            elif cmd and cmd[0] in {"python", "python3"}:
                if len(cmd) > 2 and cmd[1] == "-m" and cmd[2] == "pytest":
                    cmd = [sys.executable, "-m", "pytest", "-v", "-o", 'addopts=""'] + cmd[3:]
                else:
                    cmd = [sys.executable] + cmd[1:]

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

        # Split output into test sections by standard pytest traceback delimiter
        sections = re.split(r"^_{3,}\s+([a-zA-Z0-9_]+)\s+_{3,}$", output, flags=re.MULTILINE)
        file_line_pattern = re.compile(r"([a-zA-Z0-9_./\\-]+\.py):(\d+):")
        err_line_pattern = re.compile(r"^(?:E\s+([a-zA-Z0-9_]+Error:[^\n]+)|([a-zA-Z0-9_]+Error:[^\n]+))", re.MULTILINE)

        # sections[0] is preamble before first test header; alternating: test_name, body
        for i in range(1, len(sections), 2):
            test_name = sections[i]
            body = sections[i + 1]

            err_match = err_line_pattern.search(body)
            err_msg = (err_match.group(1) or err_match.group(2)) if err_match else "Test assertion failure"

            locations = file_line_pattern.findall(body)
            target_file = None
            target_line = 1
            target_symbol = test_name

            # Look for the last application source file in stack trace (non-test)
            for fpath, lnum in reversed(locations):
                if not any(x in fpath for x in ["test_", "_test", "site-packages"]):
                    target_file = fpath
                    target_line = int(lnum)
                    break

            # If only test files are referenced, resolve to the actual production source file via AST
            if not target_file and locations:
                test_fpath = locations[-1][0]
                resolved_src, resolved_line, resolved_sym = resolve_test_to_source(
                    project_root, test_fpath, test_name
                )
                if resolved_src:
                    target_file = resolved_src
                    target_line = resolved_line
                    target_symbol = resolved_sym or test_name
                else:
                    # Fallback to test file location if resolution fails
                    target_file = test_fpath
                    target_line = int(locations[-1][1])

            if target_file:
                # Clean up relative path
                try:
                    rel_target = str(Path(target_file).relative_to(project_root))
                except Exception:
                    rel_target = target_file

                # Extract concise evidence block from body
                evidence_lines = [
                    l for l in body.splitlines() if l.strip().startswith(">") or l.strip().startswith("E")
                ]
                evidence = "\n".join(evidence_lines).strip() or err_msg

                findings.append(
                    Finding(
                        file=rel_target,
                        line_start=max(1, target_line),
                        line_end=max(1, target_line),
                        symbol=target_symbol,
                        category=FindingCategory.TEST_FAILURE,
                        evidence=evidence,
                        detector=self.name,
                        raw_confidence=0.99,
                        description=f"Automated test '{test_name}' failed: {err_msg}",
                        metadata={"test_name": test_name, "raw_error": err_msg},
                    )
                )

        return findings
