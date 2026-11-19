"""Scoring Engine computing Severity, Confidence, Impact, and Priority with deterministic ranking."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from autopatch.core.models import Severity
from autopatch.detection.models import Finding
from autopatch.intelligence.graph import DependencyGraphs
from autopatch.scoring.confidence import ConfidenceCalculator
from autopatch.scoring.config import ScoringConfig
from autopatch.scoring.models import (
    BugCategory,
    ConfidenceBreakdown,
    ImpactBreakdown,
    PriorityScore,
    RankedBugItem,
    SeverityBreakdown,
)
from autopatch.scoring.severity import SeverityCalculator


class ScoringEngine:
    """Computes transparent multidimensional priority scoring and deterministic bug ranking."""

    def __init__(self, config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig.load_from_file()
        self.severity_calculator = SeverityCalculator(config=self.config)
        self.confidence_calculator = ConfidenceCalculator(config=self.config)

    def calculate_priority(
        self,
        category: BugCategory,
        file_path: str,
        symbol: Optional[str] = None,
        detector_agreement: float = 0.70,
        brt_status: str = "NONE",
        verification_state: str = "NONE",
        epr: float = 0.0,
        overfitting_flagged: bool = False,
        dependency_graphs: Optional[DependencyGraphs] = None,
        entry_points: Optional[List[str]] = None,
    ) -> PriorityScore:
        """Calculates Priority = severity_weight x confidence x impact with full transparency."""
        # 1. Severity Breakdown
        severity_breakdown = self.severity_calculator.compute_severity(
            category=category,
            file_path=file_path,
            symbol=symbol,
            dependency_graphs=dependency_graphs,
            entry_points=entry_points,
        )

        # 2. Confidence Breakdown
        confidence_breakdown = self.confidence_calculator.compute_confidence(
            detector_agreement=detector_agreement,
            brt_status=brt_status,
            verification_state=verification_state,
            epr=epr,
            overfitting_flagged=overfitting_flagged,
        )

        # 3. Impact Breakdown
        impact_breakdown = self._compute_impact(
            severity_breakdown=severity_breakdown,
        )

        # 4. Priority Formula: Priority = severity_weight x confidence x impact
        # Scaled by scale_factor (default 100.0)
        s_val = severity_breakdown.numeric_severity
        c_val = confidence_breakdown.overall_confidence
        i_val = impact_breakdown.impact_score

        raw_priority = s_val * c_val * i_val
        priority_score = round(raw_priority * self.config.priority.scale_factor, 2)

        # Formulate "why this rank" explanation
        explanation = (
            f"Priority Score: {priority_score:.1f}/100 "
            f"(Severity {s_val:.2f} × Confidence {c_val:.2f} × Impact {i_val:.2f}). "
            f"Severity level {severity_breakdown.severity_level.value} driven by category '{category.value}' "
            f"and reachability '{severity_breakdown.reachability_status.value}'. "
            f"Confidence {c_val * 100:.1f}% based on BRT {confidence_breakdown.brt_status} "
            f"and verification state {confidence_breakdown.verification_state}."
        )

        return PriorityScore(
            priority_score=priority_score,
            severity=severity_breakdown,
            confidence=confidence_breakdown,
            impact=impact_breakdown,
            rank=1,
            rank_explanation=explanation,
        )

    def rank_findings(
        self,
        finding_evaluations: List[Dict[str, Any]],
        dependency_graphs: Optional[DependencyGraphs] = None,
        entry_points: Optional[List[str]] = None,
    ) -> List[RankedBugItem]:
        """Calculates priority scores and deterministically ranks a collection of defect evaluations."""
        scored_items: List[RankedBugItem] = []

        for item in finding_evaluations:
            finding: Optional[Finding] = item.get("finding")
            file_path = item.get("file_path") or (finding.file if finding else "unknown.py")
            line_start = item.get("line_start") or (finding.line_start if finding else 1)
            line_end = item.get("line_end") or (finding.line_end if finding else line_start)
            symbol = item.get("symbol") or (finding.symbol if finding else None)
            desc = item.get("description") or (finding.description if finding else "Bug finding")
            evidence = item.get("evidence") or (finding.evidence if finding else "")
            cwe = item.get("cwe") or (finding.cwe if finding else None)
            bug_id = str(item.get("bug_id") or uuid4())

            raw_cat = item.get("category") or (finding.category if finding else "wrong_output")
            category = self.severity_calculator.map_category(raw_cat, cwe=cwe, desc=desc)

            det_agreement = item.get("detector_agreement") or (finding.raw_confidence if finding else 0.70)
            brt_status = item.get("brt_status", "NONE")
            verif_state = item.get("verification_state", "NONE")
            epr = item.get("epr", 0.0)
            overfit = item.get("overfitting_flagged", False)

            priority = self.calculate_priority(
                category=category,
                file_path=file_path,
                symbol=symbol,
                detector_agreement=det_agreement,
                brt_status=brt_status,
                verification_state=verif_state,
                epr=epr,
                overfitting_flagged=overfit,
                dependency_graphs=dependency_graphs,
                entry_points=entry_points,
            )

            scored_items.append(
                RankedBugItem(
                    bug_id=bug_id,
                    file_path=file_path,
                    line_start=line_start,
                    line_end=line_end,
                    symbol=symbol,
                    category=category,
                    description=desc,
                    evidence=evidence,
                    priority=priority,
                    rank=1,
                )
            )

        # Deterministic sorting:
        # 1. Primary: priority_score desc
        # 2. Secondary: numeric_severity desc
        # 3. Tertiary: overall_confidence desc
        # 4. Quaternary: impact_score desc
        # 5. Deterministic tiebreaker: file_path, line_start, bug_id
        scored_items.sort(
            key=lambda it: (
                -it.priority.priority_score,
                -it.priority.severity.numeric_severity,
                -it.priority.confidence.overall_confidence,
                -it.priority.impact.impact_score,
                it.file_path,
                it.line_start,
                it.bug_id,
            )
        )

        # Assign ranks and enrich "why this rank" explanation
        total_count = len(scored_items)
        for idx, it in enumerate(scored_items, start=1):
            it.rank = idx
            it.priority.rank = idx
            it.priority.rank_explanation = (
                f"Rank #{idx} of {total_count} bugs. "
                f"Priority score: {it.priority.priority_score:.1f}/100 "
                f"(Severity: {it.priority.severity.numeric_severity:.2f} [{it.priority.severity.severity_level.value}], "
                f"Confidence: {it.priority.confidence.overall_confidence:.2f}, "
                f"Impact: {it.priority.impact.impact_score:.2f}). "
                f"Factors: Category={it.category.value}, "
                f"BRT={it.priority.confidence.brt_status}, "
                f"Verification={it.priority.confidence.verification_state}, "
                f"Reachability={it.priority.severity.reachability_status.value}."
            )

        return scored_items

    def _compute_impact(self, severity_breakdown: SeverityBreakdown) -> ImpactBreakdown:
        reach_factor = severity_breakdown.reachability_factor
        callers = severity_breakdown.callers_count
        caller_boost = min(
            self.config.blast_radius.max_caller_boost,
            callers * self.config.blast_radius.caller_count_scale,
        )

        is_crit = severity_breakdown.is_critical_path
        crit_mult = self.config.blast_radius.critical_path_multiplier if is_crit else 1.00

        raw_impact = reach_factor * (1.0 + caller_boost) * (crit_mult / 1.35)
        impact_score = round(max(0.05, min(1.0, raw_impact)), 4)

        explanation = (
            f"Impact Score: {impact_score:.2f}. "
            f"Reachability factor={reach_factor:.2f}; "
            f"Callers={callers} (+{caller_boost:.2f} caller boost); "
            f"Critical path multiplier={crit_mult:.2f}."
        )

        return ImpactBreakdown(
            callers_count=callers,
            caller_boost=caller_boost,
            is_critical_path=is_crit,
            critical_path_multiplier=crit_mult,
            reachability_factor=reach_factor,
            impact_score=impact_score,
            explanation=explanation,
        )
