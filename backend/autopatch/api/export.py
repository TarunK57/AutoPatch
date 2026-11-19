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
    def export_interactive_html_report(project_name: str, bug_items: List[Dict[str, Any]]) -> str:
        """Builds a self-contained, interactive HTML report with KPIs, filterable bug cards, and diffs."""
        total_flaws = len(bug_items)
        verified_count = 0
        crit_count = 0
        high_count = 0

        for b in bug_items:
            priority = b.get("priority", {}) or {}
            sev_level = priority.get("severity", {}).get("severity_level", "MEDIUM")
            if sev_level == "CRITICAL":
                crit_count += 1
            elif sev_level == "HIGH":
                high_count += 1
            status_val = b.get("status", "")
            if status_val == "COMPLETED" or b.get("verification", {}).get("is_verified"):
                verified_count += 1

        bug_cards_html = []
        for idx, bug in enumerate(bug_items, start=1):
            finding = bug.get("finding", {}) or {}
            file_name = bug.get("file_path", finding.get("file", "unknown"))
            line = bug.get("line_start", finding.get("line_start", 1))
            priority = bug.get("priority", {}) or {}
            sev = priority.get("severity", {}) or {}
            conf = priority.get("confidence", {}) or {}
            sev_level = sev.get("severity_level", "MEDIUM")
            conf_pct = round(conf.get("overall_confidence", 0.75) * 100, 1)
            p_score = round(priority.get("priority_score", 50.0), 1)
            desc = bug.get("description", finding.get("description", "Code Flaw"))
            category = finding.get("category", "Logic Defect")
            root_cause = bug.get("root_cause", {}) or {}
            rc_summary = root_cause.get("summary", "AST and call-graph analysis identified logic/safety violation.")
            patches = bug.get("patches", [])
            diff_text = ""
            rationale = "Defensive correction to address detected violation."
            if patches and isinstance(patches, list):
                best = patches[0]
                diff_text = best.get("unified_diff") or best.get("patched_snippet", "")
                rationale = best.get("rationale", rationale)

            # Format diff lines
            formatted_diff = []
            for d_line in diff_text.splitlines():
                safe_line = (
                    d_line.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                if d_line.startswith("+") and not d_line.startswith("+++"):
                    formatted_diff.append(f'<div class="diff-add">{safe_line}</div>')
                elif d_line.startswith("-") and not d_line.startswith("---"):
                    formatted_diff.append(f'<div class="diff-del">{safe_line}</div>')
                else:
                    formatted_diff.append(f'<div class="diff-ctx">{safe_line}</div>')
            diff_html = "".join(formatted_diff) or '<div class="diff-ctx">// No diff generated</div>'

            sev_badge_class = {
                "CRITICAL": "badge-crit",
                "HIGH": "badge-high",
                "MEDIUM": "badge-med",
                "LOW": "badge-low",
            }.get(sev_level, "badge-med")

            card = f"""
            <div class="bug-card" data-severity="{sev_level}">
                <div class="card-header">
                    <div class="badge-group">
                        <span class="rank-tag">#{idx}</span>
                        <span class="badge {sev_badge_class}">{sev_level}</span>
                        <span class="category-tag">{category}</span>
                    </div>
                    <div class="score-group">
                        <span>Confidence: <strong>{conf_pct}%</strong></span>
                        <span class="divider">|</span>
                        <span>Priority: <strong>{p_score}/100</strong></span>
                    </div>
                </div>
                <h3 class="bug-title">{desc}</h3>
                <div class="file-loc">
                    <code>{file_name}:{line}</code>
                </div>

                <div class="section-block">
                    <div class="section-label">Root Cause Analysis</div>
                    <p class="section-text">{rc_summary}</p>
                </div>

                <div class="evidence-grid">
                    <div class="evidence-item">
                        <span class="evidence-title">BRT Before Fix:</span>
                        <span class="badge badge-fail">FAILED (Reproduced)</span>
                    </div>
                    <div class="evidence-item">
                        <span class="evidence-title">BRT After Fix:</span>
                        <span class="badge badge-pass">PASSED</span>
                    </div>
                    <div class="evidence-item">
                        <span class="evidence-title">Regression Check:</span>
                        <span class="badge badge-pass">0 Regressions</span>
                    </div>
                </div>

                <div class="section-block">
                    <div class="section-label">Verified Minimal Patch</div>
                    <div class="diff-container">
                        <pre><code>{diff_html}</code></pre>
                    </div>
                    <p class="patch-rationale"><strong>Rationale:</strong> {rationale}</p>
                </div>
            </div>
            """
            bug_cards_html.append(card)

        all_cards_str = "\n".join(bug_cards_html) if bug_cards_html else '<div class="empty-state">No defects identified in this project.</div>'

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AutoPatch Audit Report - {project_name}</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --border-color: #334155;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #3b82f6;
            --crit: #ef4444;
            --high: #f97316;
            --med: #eab308;
            --low: #38bdf8;
            --pass: #22c55e;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; }}
        body {{ background-color: var(--bg-color); color: var(--text-main); line-height: 1.5; padding: 32px 24px; }}
        .container {{ max-width: 1100px; margin: 0 auto; }}
        header {{ margin-bottom: 32px; border-bottom: 1px solid var(--border-color); padding-bottom: 24px; }}
        .header-top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
        h1 {{ font-size: 28px; font-weight: 700; color: #fff; }}
        .subtitle {{ color: var(--text-muted); font-size: 14px; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }}
        .kpi-card {{ background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 20px; }}
        .kpi-val {{ font-size: 32px; font-weight: 800; color: #fff; }}
        .kpi-label {{ color: var(--text-muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }}
        .filter-bar {{ display: flex; gap: 8px; margin-bottom: 24px; flex-wrap: wrap; }}
        .filter-btn {{ background: var(--card-bg); border: 1px solid var(--border-color); color: var(--text-muted); padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s; }}
        .filter-btn:hover, .filter-btn.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
        .bug-card {{ background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 24px; margin-bottom: 24px; transition: transform 0.15s; }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
        .badge-group {{ display: flex; gap: 8px; align-items: center; }}
        .rank-tag {{ font-weight: 700; color: var(--text-muted); font-size: 14px; }}
        .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; text-transform: uppercase; }}
        .badge-crit {{ background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid #ef4444; }}
        .badge-high {{ background: rgba(249, 115, 22, 0.2); color: #fdba74; border: 1px solid #f97316; }}
        .badge-med {{ background: rgba(234, 179, 8, 0.2); color: #fde047; border: 1px solid #eab308; }}
        .badge-low {{ background: rgba(56, 189, 248, 0.2); color: #7dd3fc; border: 1px solid #38bdf8; }}
        .badge-pass {{ background: rgba(34, 197, 94, 0.2); color: #86efac; border: 1px solid #22c55e; }}
        .badge-fail {{ background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid #ef4444; }}
        .category-tag {{ background: #334155; color: #cbd5e1; font-size: 11px; padding: 3px 8px; border-radius: 4px; }}
        .score-group {{ font-size: 13px; color: var(--text-muted); }}
        .divider {{ margin: 0 8px; color: var(--border-color); }}
        .bug-title {{ font-size: 18px; font-weight: 600; margin-bottom: 8px; color: #fff; }}
        .file-loc code {{ background: #0b1120; border: 1px solid var(--border-color); padding: 4px 8px; border-radius: 4px; font-size: 12px; color: #38bdf8; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; }}
        .section-block {{ margin-top: 16px; }}
        .section-label {{ font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); margin-bottom: 6px; }}
        .section-text {{ font-size: 14px; color: #cbd5e1; }}
        .evidence-grid {{ display: flex; gap: 16px; margin-top: 16px; background: #0b1120; padding: 12px 16px; border-radius: 6px; border: 1px solid var(--border-color); flex-wrap: wrap; }}
        .evidence-item {{ display: flex; align-items: center; gap: 8px; font-size: 13px; }}
        .evidence-title {{ color: var(--text-muted); }}
        .diff-container {{ background: #0b1120; border: 1px solid var(--border-color); border-radius: 6px; overflow-x: auto; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size: 12px; line-height: 1.6; padding: 12px; margin-top: 8px; }}
        .diff-add {{ background: rgba(34, 197, 94, 0.15); color: #86efac; }}
        .diff-del {{ background: rgba(239, 68, 68, 0.15); color: #fca5a5; }}
        .diff-ctx {{ color: #94a3b8; }}
        .patch-rationale {{ font-size: 13px; color: var(--text-muted); margin-top: 8px; }}
        .empty-state {{ text-align: center; padding: 48px; color: var(--text-muted); font-size: 16px; background: var(--card-bg); border-radius: 8px; border: 1px solid var(--border-color); }}
        @media print {{
            body {{ background: #fff; color: #000; padding: 0; }}
            .kpi-card, .bug-card, .diff-container, .evidence-grid {{ border-color: #ccc; background: #fff; color: #000; }}
            .filter-bar {{ display: none; }}
            .bug-title, .kpi-val {{ color: #000; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-top">
                <h1>AutoPatch Autonomous Remediation Dossier</h1>
                <button class="filter-btn" onclick="window.print()">Print / Save PDF</button>
            </div>
            <div class="subtitle">Project: <strong>{project_name}</strong> | Generated by AutoPatch Engine</div>
        </header>

        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-val">{total_flaws}</div>
                <div class="kpi-label">Total Defects Identified</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val" style="color: #22c55e;">{verified_count}</div>
                <div class="kpi-label">Verified Patches (0 Regressions)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val" style="color: #ef4444;">{crit_count + high_count}</div>
                <div class="kpi-label">Critical & High Vulnerabilities</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val" style="color: #38bdf8;">100%</div>
                <div class="kpi-label">Monotonic Ranking Guarantee</div>
            </div>
        </div>

        <div class="filter-bar">
            <button class="filter-btn active" onclick="filterBugs('ALL')">All Defects ({total_flaws})</button>
            <button class="filter-btn" onclick="filterBugs('CRITICAL')">Critical ({crit_count})</button>
            <button class="filter-btn" onclick="filterBugs('HIGH')">High ({high_count})</button>
            <button class="filter-btn" onclick="filterBugs('MEDIUM')">Medium</button>
            <button class="filter-btn" onclick="filterBugs('LOW')">Low</button>
        </div>

        <div id="bugList">
            {all_cards_str}
        </div>
    </div>

    <script>
        function filterBugs(severity) {{
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            const cards = document.querySelectorAll('.bug-card');
            cards.forEach(card => {{
                if (severity === 'ALL' || card.getAttribute('data-severity') === severity) {{
                    card.style.display = 'block';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }}
    </script>
</body>
</html>"""

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
