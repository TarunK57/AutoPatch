"""Export engine for AutoPatch project reports and artifacts (Diff, Markdown, SARIF, and ZIP)."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional


class ProjectExporter:
    """Exports project scan results, patches, and audit trails into standard interchange formats."""

    @staticmethod
    def export_unified_diff(patches: List[Dict[str, Any]]) -> str:
        """Concatenates unified diffs from all candidate or approved patches."""
        diff_chunks = []
        for p in patches:
            diff = p.get("unified_diff") or ""
            if diff:
                diff_chunks.append(diff.strip())
            else:
                # Generate fallback diff representation
                target_file = p.get("file", "unknown")
                orig = p.get("original_snippet", "")
                patched = p.get("patched_snippet", "")
                diff_chunks.append(
                    f"--- a/{target_file}\n+++ b/{target_file}\n"
                    f"-{orig}\n+{patched}"
                )
        return "\n\n".join(diff_chunks) + "\n"

    @staticmethod
    def export_markdown_report(project_name: str, bug_items: List[Dict[str, Any]]) -> str:
        """Builds an executive Markdown report detailing root causes, test evidence, diffs, and verification."""
        lines = [
            f"# AutoPatch Autonomous Repair Report: {project_name}",
            "",
            f"**Total Identified Flaws**: {len(bug_items)}",
            "",
            "## Executive Summary",
            "This report summarizes autonomous vulnerability detection, root cause localization,",
            "bug reproduction test (BRT) execution, and sandboxed patch verification.",
            "",
            "---",
            "",
            "## Defect & Patch Dossier",
            "",
        ]

        for idx, bug in enumerate(bug_items, start=1):
            finding = bug.get("finding", {}) or {}
            file_name = bug.get("file_path", finding.get("file", "unknown"))
            line = bug.get("line_start", finding.get("line_start", 1))
            priority = bug.get("priority", {}) or {}
            sev = priority.get("severity", {}) or {}
            conf = priority.get("confidence", {}) or {}
            patches = bug.get("patches", [])
            root_cause = bug.get("root_cause", {}) or {}

            lines.extend(
                [
                    f"### #{idx}: {bug.get('description', finding.get('description', 'Defect'))}",
                    f"- **Location**: `{file_name}:{line}`",
                    f"- **Severity**: `{sev.get('severity_level', 'MEDIUM')}` (Score: {sev.get('numeric_severity', 0.5):.2f})",
                    f"- **Confidence**: `{conf.get('overall_confidence', 0.8) * 100:.1f}%`",
                    f"- **Priority Score**: `{priority.get('priority_score', 50.0):.1f}/100`",
                    f"- **Root Cause**: {root_cause.get('summary', 'Automated AST & logic analysis')}",
                    "",
                    "#### Proposed Minimal Patch",
                    "```diff",
                ]
            )

            if patches and isinstance(patches, list):
                best_patch = patches[0]
                lines.append(best_patch.get("unified_diff") or best_patch.get("patched_snippet", "// No diff"))
                lines.append("```")
                lines.append(f"**Rationale**: {best_patch.get('rationale', 'Defensive correction')}")
            else:
                lines.append("// No patch available")
                lines.append("```")

            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def export_sarif_json(project_name: str, bug_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Formats scan findings and fixes according to the OASIS SARIF 2.1.0 standard."""
        rules: List[Dict[str, Any]] = []
        results: List[Dict[str, Any]] = []

        level_map = {
            "CRITICAL": "error",
            "HIGH": "error",
            "MEDIUM": "warning",
            "LOW": "note",
        }

        for bug in bug_items:
            finding = bug.get("finding", {}) or {}
            rule_id = finding.get("cwe") or finding.get("category", "AUTOPATCH_RULE")
            file_name = bug.get("file_path", finding.get("file", "src/unknown.py"))
            line_start = bug.get("line_start", finding.get("line_start", 1))
            line_end = bug.get("line_end", finding.get("line_end", line_start))
            desc = bug.get("description", finding.get("description", "Code defect"))
            priority = bug.get("priority", {}) or {}
            sev_level = priority.get("severity", {}).get("severity_level", "MEDIUM")

            rules.append(
                {
                    "id": str(rule_id),
                    "name": str(rule_id),
                    "shortDescription": {"text": desc},
                }
            )

            results.append(
                {
                    "ruleId": str(rule_id),
                    "level": level_map.get(sev_level, "warning"),
                    "message": {"text": desc},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": file_name},
                                "region": {
                                    "startLine": line_start,
                                    "endLine": line_end,
                                },
                            }
                        }
                    ],
                }
            )

        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "AutoPatch",
                            "semanticVersion": "1.0.0",
                            "informationUri": "https://autopatch.io",
                            "rules": rules,
                        }
                    },
                    "results": results,
                }
            ],
        }

    @staticmethod
    def export_patched_project_zip(project_dir: Path) -> bytes:
        """Packages the project directory into a zip archive bytes stream."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in project_dir.rglob("*"):
                if file_path.is_file() and not any(p in file_path.parts for p in [".git", "__pycache__", ".venv"]):
                    arcname = str(file_path.relative_to(project_dir))
                    zf.write(file_path, arcname)
        zip_buffer.seek(0)
        return zip_buffer.getvalue()
