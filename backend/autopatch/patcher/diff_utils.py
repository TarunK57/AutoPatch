"""Diff computation, minimal-diff enforcement, and git-apply compatibility verification."""

import ast
import difflib
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


def generate_unified_diff(file_path: str, original_content: str, patched_content: str) -> str:
    """Generates a standard unified diff compatible with git apply."""
    orig_lines = original_content.splitlines(keepends=True)
    patch_lines = patched_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        orig_lines,
        patch_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    )
    return "".join(diff)


def validate_minimal_diff_rules(
    original_snippet: str, patched_snippet: str, file_path: str
) -> Tuple[bool, List[str], bool]:
    """Enforces strict minimal-diff rules.

    Checks:
    - Rejects whitespace-only changes.
    - Rejects deletion of tests or assertions.
    - Flags public signature changes.

    Returns:
        (is_valid, list_of_violations, flags_signature_change)
    """
    violations: List[str] = []
    flags_signature = False

    # 1. Reject whitespace-only edits
    if re.sub(r"\s+", "", original_snippet) == re.sub(r"\s+", "", patched_snippet):
        if original_snippet != patched_snippet:
            violations.append("Rejected whitespace-only diff noise without semantic change.")
            return False, violations, False

    # 2. Reject deletion of test assertions
    if "assert " in original_snippet and "assert " not in patched_snippet:
        violations.append("Rejected deletion of existing assertions.")

    # 3. Detect and flag public function/method signature alterations
    orig_sig_match = _extract_signature(original_snippet)
    patch_sig_match = _extract_signature(patched_snippet)
    if orig_sig_match and patch_sig_match and orig_sig_match != patch_sig_match:
        flags_signature = True

    is_valid = len(violations) == 0
    return is_valid, violations, flags_signature


def _extract_signature(snippet: str) -> Optional[str]:
    for line in snippet.splitlines():
        line_clean = line.strip()
        if line_clean.startswith("def ") or line_clean.startswith("function ") or "public " in line_clean:
            return line_clean
    return None


def verify_patch_applies_cleanly(
    project_root: Path,
    file_path: str,
    original_snippet: str,
    patched_snippet: str,
) -> Tuple[bool, Optional[str]]:
    """Verifies that the original snippet matches exactly and the patched file is syntactically valid."""
    full_path = (project_root / file_path).resolve()
    if not full_path.is_file():
        return False, f"Target file does not exist: {file_path}"

    content = full_path.read_text(encoding="utf-8", errors="replace")

    # 1. Exact string match check
    if original_snippet not in content:
        # Check normalized newline match
        if original_snippet.replace("\r\n", "\n") not in content.replace("\r\n", "\n"):
            return False, f"Original snippet does not match target file contents in '{file_path}'."

    # 2. Syntax validation on patched content
    patched_full_content = content.replace(original_snippet, patched_snippet, 1)

    if file_path.endswith(".py"):
        try:
            ast.parse(patched_full_content, filename=file_path)
        except SyntaxError as e:
            return False, f"Python SyntaxError in patched content: {str(e)}"

    return True, None
