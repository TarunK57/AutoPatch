"""Evaluation and calibration of scoring engine against the 15-bug seeded benchmark repository.

Calibrated Weight Structure:
1. Category Weights:
   - Security: 1.00 (SQLi, Command Injection, Secrets)
   - Data Loss: 0.85 (Unclosed resources, leaked state)
   - Crash: 0.70 (Zero division, unhandled null/exception)
   - Wrong Output: 0.50 (Off-by-one, range validation, mutable default)
   - Style: 0.20 (Unreachable dead code, lint formatting)
2. Confidence Weights:
   - BRT Reproduction: 0.35 (Primary truth anchor)
   - Detector Agreement: 0.25 (Multi-detector consensus)
   - Verification State: 0.25 (Sandbox verification outcome)
   - EPR: 0.15 (Ensemble reproduction pass rate)
   - Overfitting Penalty: -0.30
3. Priority Formula:
   - Priority = Severity × Confidence × Impact × 100
"""

from pathlib import Path
import pytest

from autopatch.detection.pipeline import DetectionPipeline
from autopatch.intelligence.service import CodeIntelligenceService
from autopatch.scoring.engine import ScoringEngine
from autopatch.scoring.models import BugCategory
from tests.test_detection_seeded_repo import seeded_repo


def test_scoring_calibration_on_15_seeded_bugs(seeded_repo):
    """Calibrates and validates ranking across the 15 seeded benchmark bugs."""
    root, known_bugs = seeded_repo

    # 1. Index the seeded repo
    intel_service = CodeIntelligenceService()
    project_id = "eval_scoring_seeded_15"
    intel_service.index_project(project_id, root)

    # 2. Parse AST indices
    file_indices = []
    for p in root.glob("*.*"):
        adapter = intel_service.get_adapter_for_path(p)
        if adapter:
            file_indices.append(adapter.parse_file(p.name, p.read_text(encoding="utf-8")))

    # 3. Run detection pipeline
    pipeline = DetectionPipeline()
    report = pipeline.run(project_id, root, file_indices)

    findings = report.findings
    assert len(findings) >= 15

    # 4. Formulate evaluation items simulating reproduction & verification
    eval_items = []
    for f in findings:
        item = {
            "finding": f,
            "file_path": f.file,
            "line_start": f.line_start,
            "category": f.category.value,
            "description": f.description,
            "cwe": f.cwe,
            "detector_agreement": f.raw_confidence,
        }

        # Simulate confirmed BRT and verification state based on bug nature
        if f.cwe or "security" in f.file.lower():
            item["brt_status"] = "CONFIRMED"
            item["verification_state"] = "VERIFIED"
            item["epr"] = 100.0
        elif "zero" in f.description.lower() or "average" in f.description.lower():
            item["brt_status"] = "CONFIRMED"
            item["verification_state"] = "VERIFIED"
            item["epr"] = 100.0
        elif "unreachable" in f.description.lower():
            item["brt_status"] = "NONE"
            item["verification_state"] = "NONE"
            item["epr"] = 0.0
        else:
            item["brt_status"] = "CONFIRMED"
            item["verification_state"] = "PLAUSIBLE_BUT_UNVERIFIED"
            item["epr"] = 50.0

        eval_items.append(item)

    # 5. Rank all findings using ScoringEngine
    scoring_engine = ScoringEngine()
    ranked = scoring_engine.rank_findings(
        finding_evaluations=eval_items,
        dependency_graphs=intel_service.get_graphs(project_id),
        entry_points=["security_bugs.py", "python_bugs.py"],
    )

    assert len(ranked) == len(eval_items)

    # 5. Calibration verification on ranked tiers:
    # Top 3 items MUST be critical Security vulnerabilities
    top_3_categories = [r.category for r in ranked[:3]]
    for cat in top_3_categories:
        assert cat == BugCategory.SECURITY, f"Expected top 3 to be SECURITY, got {cat}"

    # Specifically, SQL Injection or Command Injection must have the highest scores
    top_descriptions = " ".join(r.description.lower() for r in ranked[:3])
    assert "sql" in top_descriptions or "command" in top_descriptions or "secret" in top_descriptions

    # Bottom items MUST be style / dead code / lint issues
    lowest_item = ranked[-1]
    assert lowest_item.category in {BugCategory.STYLE, BugCategory.WRONG_OUTPUT}
    assert "unreachable" in lowest_item.description.lower() or lowest_item.category == BugCategory.STYLE

    # Monotonic priority range: scores must be properly calibrated between 0 and 100
    for r in ranked:
        assert 0.0 <= r.priority.priority_score <= 100.0
        assert r.priority.severity.numeric_severity > 0.0
        assert r.priority.confidence.overall_confidence > 0.0
        assert r.priority.impact.impact_score > 0.0
        # Ensure 'why this rank' explanation is present
        assert len(r.priority.rank_explanation) > 20

    # Ensure rank ordering is strictly descending
    for i in range(len(ranked) - 1):
        assert ranked[i].priority.priority_score >= ranked[i + 1].priority.priority_score
