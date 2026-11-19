"""Configuration models for AutoPatch scoring and prioritization.

Enforces:
- Weights live in configuration, not in hardcoded logic.
- Configurable category weights, reachability factors, blast radius keywords, and confidence component weights.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


DEFAULT_CONFIG_PATH = Path(__file__).parent / "scoring_config.json"


class CategoryWeights(BaseModel):
    security: float = 1.00
    data_loss: float = 0.85
    crash: float = 0.70
    wrong_output: float = 0.50
    style: float = 0.20


class ReachabilityWeights(BaseModel):
    entry_point_direct: float = 1.00
    entry_point_indirect: float = 0.80
    public_api: float = 0.70
    internal_reachable: float = 0.50
    unreachable: float = 0.20


class BlastRadiusConfig(BaseModel):
    critical_path_multiplier: float = 1.35
    caller_count_scale: float = 0.05
    max_caller_boost: float = 0.40
    critical_path_keywords: List[str] = Field(
        default_factory=lambda: [
            "auth",
            "login",
            "token",
            "payment",
            "checkout",
            "billing",
            "security",
            "crypto",
            "password",
            "secret",
            "user",
            "session",
            "db",
            "database",
            "execute",
            "query",
            "api",
            "route",
            "main",
            "server",
            "admin",
        ]
    )


class ConfidenceWeights(BaseModel):
    detector_agreement: float = 0.25
    brt_reproduction: float = 0.35
    verification_state: float = 0.25
    epr: float = 0.15
    overfitting_penalty: float = 0.30


class PriorityConfig(BaseModel):
    severity_weight: float = 0.45
    confidence_weight: float = 0.35
    impact_weight: float = 0.20
    scale_factor: float = 100.0


class ScoringConfig(BaseModel):
    """Root configuration object containing all calibrated scoring parameters."""

    version: str = "1.0.0"
    description: str = "AutoPatch Scoring Configuration"
    category_weights: CategoryWeights = Field(default_factory=CategoryWeights)
    reachability_weights: ReachabilityWeights = Field(default_factory=ReachabilityWeights)
    blast_radius: BlastRadiusConfig = Field(default_factory=BlastRadiusConfig)
    confidence_weights: ConfidenceWeights = Field(default_factory=ConfidenceWeights)
    verification_state_scores: Dict[str, float] = Field(
        default_factory=lambda: {
            "VERIFIED": 1.00,
            "PLAUSIBLE_BUT_UNVERIFIED": 0.65,
            "NEEDS_REVIEW": 0.40,
            "FAILED": 0.05,
        }
    )
    brt_status_scores: Dict[str, float] = Field(
        default_factory=lambda: {
            "CONFIRMED": 1.00,
            "UNCONFIRMED": 0.25,
            "NONE": 0.10,
        }
    )
    priority: PriorityConfig = Field(default_factory=PriorityConfig)

    @classmethod
    def load_from_file(cls, path: Optional[Path] = None) -> ScoringConfig:
        """Loads configuration from JSON file. Falls back to default JSON file or defaults."""
        target_path = path or DEFAULT_CONFIG_PATH
        if target_path and target_path.is_file():
            try:
                data = json.loads(target_path.read_text(encoding="utf-8"))
                return cls(**data)
            except Exception:
                pass
        return cls()
