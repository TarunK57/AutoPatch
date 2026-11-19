"""Code Hotspot Detection analyzing Git churn, author dispersion, and architectural complexity."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HotspotFileItem(BaseModel):
    file_path: str
    hotspot_score: float = Field(ge=0.0, le=100.0)
    risk_tier: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    commit_count: int = 0
    unique_authors_count: int = 0
    lines_of_code: int = 0
    finding_count: int = 0
    churn_volume: int = 0  # added + deleted lines
    explanation: str
    recommendation: str


class HotspotAnalysisReport(BaseModel):
    project_id: str
    total_files_analyzed: int
    critical_hotspots_count: int
    high_risk_count: int
    medium_risk_count: int
    average_hotspot_score: float
    hotspots: List[HotspotFileItem] = Field(default_factory=list)


class CodeHotspotAnalyzer:
    """
    Identifies high-risk code hotspots by combining Git version control churn,
    author diversity, and static code complexity.
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()

    def analyze_hotspots(
        self,
        project_id: str,
        findings: Optional[List[Dict[str, Any]]] = None,
        max_results: int = 25,
    ) -> HotspotAnalysisReport:
        findings = findings or []
        findings_by_file: Dict[str, int] = {}
        for f in findings:
            f_path = f.get("file", "")
            if f_path:
                findings_by_file[f_path] = findings_by_file.get(f_path, 0) + 1

        # 1. Collect all eligible source files
        source_files: List[Path] = []
        for ext in ("*.py", "*.js", "*.ts", "*.go", "*.c", "*.cpp", "*.java"):
            for p in self.project_root.rglob(ext):
                rel = str(p.relative_to(self.project_root))
                if any(part.startswith(".") or part in ("venv", ".venv", "node_modules", "dist", "build") for part in p.parts):
                    continue
                source_files.append(p)

        # 2. Extract Git Churn Metrics (if git repo exists)
        git_stats = self._extract_git_churn()

        # 3. Calculate Hotspot Score per file
        items: List[HotspotFileItem] = []
        for file_path in source_files:
            rel_str = str(file_path.relative_to(self.project_root))
            loc = self._count_loc(file_path)
            f_findings = findings_by_file.get(rel_str, 0)

            stats = git_stats.get(rel_str, {
                "commits": 1,
                "authors": 1,
                "churn": 0,
            })

            commits = stats.get("commits", 1)
            authors = stats.get("authors", 1)
            churn = stats.get("churn", 0)

            # Scoring weights:
            # 35% commit frequency + 25% author dispersion + 25% findings + 15% LOC complexity
            norm_commits = min(commits / 15.0, 1.0) * 35.0
            norm_authors = min(authors / 5.0, 1.0) * 25.0
            norm_findings = min(f_findings / 3.0, 1.0) * 25.0
            norm_loc = min(loc / 400.0, 1.0) * 15.0

            raw_score = round(norm_commits + norm_authors + norm_findings + norm_loc, 1)
            hotspot_score = max(5.0, min(raw_score, 100.0))

            if hotspot_score >= 70.0:
                risk_tier = "CRITICAL"
                rec = "Urgent modular decomposition and comprehensive regression verification required."
            elif hotspot_score >= 50.0:
                risk_tier = "HIGH"
                rec = "Add behavioral invariant tests and isolate high-churn business logic."
            elif hotspot_score >= 25.0:
                risk_tier = "MEDIUM"
                rec = "Monitor pull requests and enforce code review consensus on changes."
            else:
                risk_tier = "LOW"
                rec = "Code structure stable with minimal churn."

            explanation = (
                f"Hotspot score {hotspot_score}/100: Modified across {commits} commit(s) by {authors} author(s) "
                f"with {loc} LOC and {f_findings} known defect(s)."
            )

            items.append(
                HotspotFileItem(
                    file_path=rel_str,
                    hotspot_score=hotspot_score,
                    risk_tier=risk_tier,
                    commit_count=commits,
                    unique_authors_count=authors,
                    lines_of_code=loc,
                    finding_count=f_findings,
                    churn_volume=churn,
                    explanation=explanation,
                    recommendation=rec,
                )
            )

        # Sort descending by hotspot score
        items.sort(key=lambda x: -x.hotspot_score)
        top_items = items[:max_results]

        critical_count = sum(1 for it in top_items if it.risk_tier == "CRITICAL")
        high_count = sum(1 for it in top_items if it.risk_tier == "HIGH")
        medium_count = sum(1 for it in top_items if it.risk_tier == "MEDIUM")
        avg_score = round(sum(it.hotspot_score for it in top_items) / max(len(top_items), 1), 1)

        return HotspotAnalysisReport(
            project_id=project_id,
            total_files_analyzed=len(items),
            critical_hotspots_count=critical_count,
            high_risk_count=high_count,
            medium_risk_count=medium_count,
            average_hotspot_score=avg_score,
            hotspots=top_items,
        )

    def _extract_git_churn(self) -> Dict[str, Dict[str, Any]]:
        """Parses git log history to count commits, authors, and line churn per file."""
        stats: Dict[str, Dict[str, Any]] = {}
        git_dir = self.project_root / ".git"
        if not git_dir.exists():
            return stats

        try:
            # Run git log with author and numstat
            cmd = ["git", "log", "--pretty=format:COMMIT|%an", "--numstat", "-n", "100"]
            res = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                return stats

            current_author = "Unknown"
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("COMMIT|"):
                    current_author = line.split("|", 1)[1]
                else:
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        added, deleted, path_str = parts[0], parts[1], parts[2]
                        if path_str not in stats:
                            stats[path_str] = {
                                "commits": 0,
                                "authors_set": set(),
                                "churn": 0,
                            }
                        stats[path_str]["commits"] += 1
                        stats[path_str]["authors_set"].add(current_author)
                        try:
                            stats[path_str]["churn"] += int(added) + int(deleted)
                        except ValueError:
                            pass

            # Convert authors_set to count
            for p, d in stats.items():
                d["authors"] = len(d.pop("authors_set", set()))

        except Exception:
            pass

        return stats

    def _count_loc(self, file_path: Path) -> int:
        try:
            return len(file_path.read_text(encoding="utf-8", errors="replace").splitlines())
        except Exception:
            return 0
