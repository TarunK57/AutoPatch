"""Data models and breakdown structures for Severity, Confidence, Impact, and Priority."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from autopatch.core.models import Severity


class BugCategory(str, Enum):
    """Categorical classification of defects with deterministic severity ordering."""

    SECURITY = "security"
    DATA_LOSS = "data_loss"
    CRASH = "crash"
    WRONG_OUTPUT = "wrong_output"
    STYLE = "style"

    @property
    def rank(self) -> int:
        ranks = {
            BugCategory.SECURITY: 5,
            BugCategory.DATA_LOSS: 4,
            BugCategory.CRASH: 3,
            BugCategory.WRONG_OUTPUT: 2,
            BugCategory.STYLE: 1,
        }
        return ranks[self]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, BugCategory):
            return NotImplemented
        return self.rank < other.rank

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, BugCategory):
            return NotImplemented
        return self.rank > other.rank


class ReachabilityStatus(str, Enum):
    """Classification of symbol reachability from application entry points."""

    ENTRY_POINT_DIRECT = "entry_point_direct"
    ENTRY_POINT_INDIRECT = "entry_point_indirect"
    PUBLIC_API = "public_api"
    INTERNAL_REACHABLE = "internal_reachable"
    UNREACHABLE = "unreachable"


class SeverityBreakdown(BaseModel):
    """Detailed attribution of bug severity calculation."""

    category: BugCategory
    category_base_weight: float = Field(ge=0.0, le=1.0)
    reachability_status: ReachabilityStatus
    reachability_factor: float = Field(ge=0.0, le=1.0)
    reachability_path: List[str] = Field(default_factory=list)
    callers_count: int = Field(ge=0, default=0)
    is_critical_path: bool = False
    critical_keywords_matched: List[str] = Field(default_factory=list)
    blast_radius_multiplier: float = Field(ge=1.0)
    numeric_severity: float = Field(ge=0.0, le=1.0)
    severity_level: Severity
    explanation: str = Field(min_length=10)


class ConfidenceBreakdown(BaseModel):
    """Detailed attribution of calibrated confidence calculation."""

    detector_agreement_score: float = Field(ge=0.0, le=1.0)
    detector_agreement_weighted: float
    brt_status: str  # "CONFIRMED", "UNCONFIRMED", "NONE"
    brt_score: float = Field(ge=0.0, le=1.0)
    brt_weighted: float
    verification_state: str  # "VERIFIED", "PLAUSIBLE_BUT_UNVERIFIED", "NEEDS_REVIEW", "FAILED"
    verification_score: float = Field(ge=0.0, le=1.0)
    verification_weighted: float
    epr: float = Field(ge=0.0, le=100.0)
    epr_score: float = Field(ge=0.0, le=1.0)
    epr_weighted: float
    overfitting_flagged: bool = False
    overfitting_penalty: float = Field(ge=0.0, le=1.0, default=0.0)
    overall_confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = Field(min_length=10)


class ImpactBreakdown(BaseModel):
    """Attribution of collateral defect impact based on callers, critical paths, and exposure."""

    callers_count: int = Field(ge=0, default=0)
    caller_boost: float = Field(ge=0.0, le=1.0)
    is_critical_path: bool = False
    critical_path_multiplier: float = Field(ge=1.0)
    reachability_factor: float = Field(ge=0.0, le=1.0)
    impact_score: float = Field(ge=0.0, le=1.0)
    explanation: str = Field(min_length=10)


class PriorityScore(BaseModel):
    """Overall priority score with full transparency breakdown for the UI."""

    priority_score: float = Field(ge=0.0, le=100.0)
    severity: SeverityBreakdown
    confidence: ConfidenceBreakdown
    impact: ImpactBreakdown
    rank: int = 1
    rank_explanation: str = Field(min_length=10)


class RankedBugItem(BaseModel):
    """A ranked bug item complete with location, evidence, and scoring dossier."""

    bug_id: str
    file_path: str
    line_start: int
    line_end: int
    symbol: Optional[str] = None
    category: BugCategory
    description: str
    evidence: str = ""
    priority: PriorityScore
    rank: int = 1
