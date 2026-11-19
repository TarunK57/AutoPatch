"""Adapters for static linters and security scanners (Ruff, ESLint, Bandit, Semgrep).

Runs tools inside the sandbox and normalizes disparate JSON/CLI outputs into the uniform Finding schema.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from autopatch.detection.base import BaseDetector, CancellationToken
from autopatch.detection.models import Finding, FindingCategory
from autopatch.intelligence.models import FileASTIndex


class LinterSuiteAdapter(BaseDetector):
    """Executes sandboxed static linters (ruff, eslint, bandit, semgrep) and normalizes outputs."""

    @property
    def name(self) -> str:
        return "LINTER_SUITE"

    def detect(
        self,
        project_root: Path,
        file_indices: List[FileASTIndex],
        cancel_token: Optional[CancellationToken] = None,
    ) -> List[Finding]:
        findings: List[Finding] = []

        if cancel_token:
            cancel_token.check_cancelled()

        # Execute available tools
        findings.extend(self.run_ruff(project_root))
        if cancel_token:
            cancel_token.check_cancelled()

        findings.extend(self.run_bandit(project_root))
        if cancel_token:
            cancel_token.check_cancelled()

        findings.extend(self.run_eslint(project_root))
        if cancel_token:
            cancel_token.check_cancelled()

        findings.extend(self.run_semgrep(project_root))

        return findings

    def run_ruff(self, project_root: Path) -> List[Finding]:
        """Runs Ruff linter and normalizes JSON output."""
        findings: List[Finding] = []
        if not shutil.which("ruff"):
            return findings

        try:
            cmd = ["ruff", "check", "--output-format=json", str(project_root)]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
            if res.stdout:
                data = json.loads(res.stdout)
                for item in data:
                    findings.append(self.normalize_ruff_finding(item, project_root))
        except Exception:
            pass

        return findings

    def normalize_ruff_finding(self, item: Dict[str, Any], project_root: Path) -> Finding:
        full_path = Path(item.get("filename", ""))
        try:
            rel_path = str(full_path.relative_to(project_root))
        except Exception:
            rel_path = full_path.name

        start_line = item.get("location", {}).get("row", 1)
        end_line = item.get("end_location", {}).get("row", start_line)
        code = item.get("code", "")
        message = item.get("message", "Ruff issue")

        # Try to read line from file for evidence
        evidence = f"{code}: {message}"
        try:
            lines = (project_root / rel_path).read_text(encoding="utf-8").splitlines()
            if 0 < start_line <= len(lines):
                evidence = lines[start_line - 1].strip() or evidence
        except Exception:
            pass

        return Finding(
            file=rel_path,
            line_start=start_line,
            line_end=end_line,
            category=FindingCategory.STYLE_LINT,
            cwe=None,
            evidence=evidence,
            detector="RUFF",
            raw_confidence=0.85,
            description=f"[{code}] {message}",
            metadata={"rule_code": code},
        )

    def run_bandit(self, project_root: Path) -> List[Finding]:
        """Runs Bandit Python security scanner and normalizes JSON output."""
        findings: List[Finding] = []
        if not shutil.which("bandit"):
            return findings

        try:
            cmd = ["bandit", "-f", "json", "-r", str(project_root)]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
            if res.stdout:
                data = json.loads(res.stdout)
                for item in data.get("results", []):
                    findings.append(self.normalize_bandit_finding(item, project_root))
        except Exception:
            pass

        return findings

    def normalize_bandit_finding(self, item: Dict[str, Any], project_root: Path) -> Finding:
        full_path = Path(item.get("filename", ""))
        try:
            rel_path = str(full_path.relative_to(project_root))
        except Exception:
            rel_path = full_path.name

        line_num = item.get("line_number", 1)
        line_range = item.get("line_range", [line_num])
        end_line = max(line_range) if line_range else line_num

        issue_text = item.get("issue_text", "")
        test_id = item.get("test_id", "")
        cwe_info = item.get("issue_cwe", {})
        cwe_id = f"CWE-{cwe_info.get('id')}" if cwe_info.get("id") else None

        evidence = item.get("code", "").strip() or f"Line {line_num}: {issue_text}"

        return Finding(
            file=rel_path,
            line_start=line_num,
            line_end=end_line,
            category=FindingCategory.SECURITY,
            cwe=cwe_id,
            evidence=evidence,
            detector="BANDIT",
            raw_confidence=0.90,
            description=f"[{test_id}] {issue_text}",
            metadata={"confidence": item.get("issue_confidence"), "severity": item.get("issue_severity")},
        )

    def run_eslint(self, project_root: Path) -> List[Finding]:
        """Runs ESLint and normalizes JSON output."""
        findings: List[Finding] = []
        if not shutil.which("eslint"):
            return findings

        try:
            cmd = ["eslint", "-f", "json", str(project_root)]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
            if res.stdout:
                data = json.loads(res.stdout)
                for file_entry in data:
                    findings.extend(self.normalize_eslint_file(file_entry, project_root))
        except Exception:
            pass

        return findings

    def normalize_eslint_file(self, file_entry: Dict[str, Any], project_root: Path) -> List[Finding]:
        findings: List[Finding] = []
        full_path = Path(file_entry.get("filePath", ""))
        try:
            rel_path = str(full_path.relative_to(project_root))
        except Exception:
            rel_path = full_path.name

        for msg in file_entry.get("messages", []):
            line = msg.get("line", 1)
            end_line = msg.get("endLine", line)
            rule = msg.get("ruleId", "eslint")
            text = msg.get("message", "Lint issue")
            evidence = f"Line {line}: {text}"

            try:
                src_lines = (project_root / rel_path).read_text(encoding="utf-8").splitlines()
                if 0 < line <= len(src_lines):
                    evidence = src_lines[line - 1].strip() or evidence
            except Exception:
                pass

            findings.append(
                Finding(
                    file=rel_path,
                    line_start=line,
                    line_end=end_line,
                    category=FindingCategory.STYLE_LINT,
                    cwe=None,
                    evidence=evidence,
                    detector="ESLINT",
                    raw_confidence=0.85,
                    description=f"[{rule}] {text}",
                    metadata={"ruleId": rule},
                )
            )

        return findings

    def run_semgrep(self, project_root: Path) -> List[Finding]:
        """Runs Semgrep and normalizes JSON output."""
        findings: List[Finding] = []
        if not shutil.which("semgrep"):
            return findings

        try:
            cmd = ["semgrep", "--json", str(project_root)]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
            if res.stdout:
                data = json.loads(res.stdout)
                for item in data.get("results", []):
                    findings.append(self.normalize_semgrep_finding(item, project_root))
        except Exception:
            pass

        return findings

    def normalize_semgrep_finding(self, item: Dict[str, Any], project_root: Path) -> Finding:
        full_path = Path(item.get("path", ""))
        try:
            rel_path = str(full_path.relative_to(project_root))
        except Exception:
            rel_path = full_path.name

        start = item.get("start", {}).get("line", 1)
        end = item.get("end", {}).get("line", start)
        check_id = item.get("check_id", "semgrep")
        extra = item.get("extra", {})
        message = extra.get("message", "Semgrep finding")
        lines = extra.get("lines", "").strip() or f"Line {start}: {message}"

        # Extract metadata CWE if present
        cwe_list = extra.get("metadata", {}).get("cwe", [])
        cwe_str = cwe_list[0] if isinstance(cwe_list, list) and cwe_list else None

        return Finding(
            file=rel_path,
            line_start=start,
            line_end=end,
            category=FindingCategory.SECURITY if cwe_str else FindingCategory.LOGIC_ERROR,
            cwe=cwe_str,
            evidence=lines,
            detector="SEMGREP",
            raw_confidence=0.92,
            description=f"[{check_id}] {message}",
            metadata={"check_id": check_id},
        )
