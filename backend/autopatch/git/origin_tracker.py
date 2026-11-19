"""Bug Origin Detection engine tracing defect introductions to exact commits and authors via Git archaeology."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from autopatch.core.logging import get_logger

logger = get_logger(__name__)


class BugOriginInfo(BaseModel):
    bug_id: str
    file_path: str
    line_number: int
    commit_sha: str
    short_sha: str
    author_name: str
    author_email: str
    commit_date: str
    commit_summary: str
    age_in_days: int
    pr_reference: Optional[str] = None
    culprit_code_line: str
    origin_classification: str  # "LEGACY_CODEBASE", "RECENT_REGRESSION", "UNCOMMITTED_LOCAL_CHANGE"


class BugOriginTracker:
    """Traces defects to their introducing commits, authors, and pull requests."""

    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir.resolve()

    def trace_origin(
        self,
        bug_id: str,
        file_path: str,
        line_number: int,
    ) -> BugOriginInfo:
        """Runs git blame to identify the commit that introduced line_number."""
        full_path = self.repo_dir / file_path
        culprit_line = ""

        if full_path.is_file():
            try:
                lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
                if 1 <= line_number <= len(lines):
                    culprit_line = lines[line_number - 1].strip()
            except Exception:
                pass

        # Check if git repository exists
        if not (self.repo_dir / ".git").exists():
            return self._build_fallback_origin(
                bug_id=bug_id,
                file_path=file_path,
                line_number=line_number,
                culprit_line=culprit_line,
                reason="Repository not under Git version control",
            )

        try:
            # Run git blame with porcelain format
            cmd = ["git", "blame", "-L", f"{line_number},{line_number}", "--porcelain", file_path]
            res = subprocess.run(
                cmd,
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True,
                check=False,
            )

            if res.returncode != 0 or not res.stdout:
                return self._build_fallback_origin(
                    bug_id=bug_id,
                    file_path=file_path,
                    line_number=line_number,
                    culprit_line=culprit_line,
                    reason="Line modified in working tree without commit",
                )

            # Parse porcelain blame output
            parsed = self._parse_porcelain_blame(res.stdout)
            commit_sha = parsed.get("sha", "0000000000000000000000000000000000000000")
            short_sha = commit_sha[:8]
            author = parsed.get("author", "Local Developer")
            author_email = parsed.get("author-mail", "<local@workspace>").strip("<>")
            summary = parsed.get("summary", "Working directory change")
            timestamp_sec = int(parsed.get("author-time", 0))

            if timestamp_sec > 0:
                dt = datetime.fromtimestamp(timestamp_sec, tz=timezone.utc)
                dt_iso = dt.isoformat()
                age_days = max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 86400))
            else:
                dt_iso = datetime.now(timezone.utc).isoformat()
                age_days = 0

            # Check PR reference in commit message (e.g. #42 or pull/42)
            pr_ref = None
            import re
            pr_match = re.search(r"#(\d+)", summary)
            if pr_match:
                pr_ref = f"PR #{pr_match.group(1)}"

            # Classification
            if commit_sha.startswith("00000000"):
                classification = "UNCOMMITTED_LOCAL_CHANGE"
            elif age_days <= 14:
                classification = "RECENT_REGRESSION"
            else:
                classification = "LEGACY_CODEBASE"

            return BugOriginInfo(
                bug_id=bug_id,
                file_path=file_path,
                line_number=line_number,
                commit_sha=commit_sha,
                short_sha=short_sha,
                author_name=author,
                author_email=author_email,
                commit_date=dt_iso,
                commit_summary=summary,
                age_in_days=age_days,
                pr_reference=pr_ref,
                culprit_code_line=culprit_line or parsed.get("line_content", f"Line {line_number}"),
                origin_classification=classification,
            )

        except Exception as e:
            logger.warning(f"Git blame failed for {file_path}:{line_number}: {e}")
            return self._build_fallback_origin(
                bug_id=bug_id,
                file_path=file_path,
                line_number=line_number,
                culprit_line=culprit_line,
                reason=str(e),
            )

    def _parse_porcelain_blame(self, output: str) -> Dict[str, Any]:
        """Parses git blame --porcelain header-value lines."""
        lines = output.splitlines()
        data: Dict[str, Any] = {}
        if lines:
            first_line = lines[0].split()
            if first_line:
                data["sha"] = first_line[0]

        for l in lines[1:]:
            if l.startswith("\t"):
                data["line_content"] = l[1:].strip()
                break
            parts = l.split(" ", 1)
            if len(parts) == 2:
                data[parts[0]] = parts[1]

        return data

    def _build_fallback_origin(
        self,
        bug_id: str,
        file_path: str,
        line_number: int,
        culprit_line: str,
        reason: str,
    ) -> BugOriginInfo:
        return BugOriginInfo(
            bug_id=bug_id,
            file_path=file_path,
            line_number=line_number,
            commit_sha="0000000000000000000000000000000000000000",
            short_sha="local",
            author_name="Local Author",
            author_email="developer@local",
            commit_date=datetime.now(timezone.utc).isoformat(),
            commit_summary=f"Uncommitted modification ({reason})",
            age_in_days=0,
            pr_reference=None,
            culprit_code_line=culprit_line or f"# {file_path}:{line_number}",
            origin_classification="UNCOMMITTED_LOCAL_CHANGE",
        )
