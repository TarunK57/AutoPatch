"""Scoring and prioritization subsystem for AutoPatch.

Provides:
- ScoringConfig: externalized configuration for weights and parameters.
- SeverityCalculator: multidimensional severity calculation (category, reachability, blast radius).
- ConfidenceCalculator: calibrated confidence with formal monotonicity bounds.
- ScoringEngine: deterministic ranking and priority computation with "why this rank" transparency.
- Domain models: BugCategory, SeverityBreakdown, ConfidenceBreakdown, ImpactBreakdown, PriorityScore, RankedBugItem.
"""

from autopatch.scoring.confidence import ConfidenceCalculator
from autopatch.scoring.config import ScoringConfig
from autopatch.scoring.engine import ScoringEngine
from autopatch.scoring.models import (
    BugCategory,
    ConfidenceBreakdown,
    ImpactBreakdown,
    PriorityScore,
    RankedBugItem,
    ReachabilityStatus,
    SeverityBreakdown,
)
from autopatch.scoring.severity import SeverityCalculator

__all__ = [
    "ScoringConfig",
    "SeverityCalculator",
    "ConfidenceCalculator",
    "ScoringEngine",
    "BugCategory",
    "ReachabilityStatus",
    "SeverityBreakdown",
    "ConfidenceBreakdown",
    "ImpactBreakdown",
    "PriorityScore",
    "RankedBugItem",
]
