"""Data models for evaluation dataset instances, benchmark configurations, and evaluation metrics."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BugCategory(str, Enum):
    """Categorical taxonomy for seeded and benchmark defects."""
    OFF_BY_ONE = "off-by-one"
    VALIDATION = "validation"
    NULL_ACCESS = "null access"
    SECURITY = "security"
    CONCURRENCY_LITE = "concurrency-lite"
    WRONG_OPERATOR = "wrong operator"
    BOUNDARY = "boundary"


class Language(str, Enum):
    """Supported source languages in the evaluation harness."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"


class EvaluationInstance(BaseModel):
    """
    Representation of an individual bug instance in the benchmark.
    Contains buggy code, ground-truth fix, baseline tests, and hidden oracle test.
    """
    instance_id: str
    language: Language
    category: BugCategory
    description: str
    file_path: str
    target_symbol: str
    line_start: int
    line_end: int
    buggy_code: str
    ground_truth_patch: str
    ground_truth_code: str
    hidden_oracle_test: str
    existing_tests: str = ""
    test_runner_command: Optional[str] = None
    source: str = "seeded"  # "seeded" or "swe-bench-lite"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AutoCodeRoverFailureCategory(str, Enum):
    """AutoCodeRover failure taxonomy for deep defect analysis."""
    WRONG_LOCATION = "Wrong Location"
    NO_PATCH = "No Patch"
    WRONG_PATCH = "Wrong Patch"
    OVERFITTED_PATCH = "Overfitted Patch"
    REGRESSION_FAILURE = "Regression Failure"
    BRT_FAILURE = "BRT Failure"
    NONE = "None (Fixed)"


class InstanceEvaluationResult(BaseModel):
    """Detailed outcomes for a single evaluation instance."""
    instance_id: str
    language: Language
    category: BugCategory
    detected: bool = False
    localization_rank: int = -1  # 1 for top-1, 2 for top-2, -1 if not found
    localized_hit_at_1: bool = False
    localized_hit_at_3: bool = False
    candidate_brt_generated: bool = False
    candidate_brt_passed_on_buggy: bool = False  # Should fail on buggy
    plausible_brt_confirmed: bool = False        # Passes on ground truth fix
    patch_synthesized: bool = False
    patch_applies_cleanly: bool = False
    patch_plausible: bool = False                # Passes hidden oracle test
    patch_correct: bool = False                  # Equivalence to ground truth
    regression_detected: bool = False            # Broke existing tests
    epr_rank: int = 1
    epr_score: float = 0.0
    epr_top_1_precision: bool = False
    duration_seconds: float = 0.0
    cost_usd: float = 0.0
    failure_category: AutoCodeRoverFailureCategory = AutoCodeRoverFailureCategory.NONE
    failure_reason: str = ""
    candidate_patch_diff: str = ""


class MetricWithCI(BaseModel):
    """Scalar metric with 95% confidence intervals from bootstrap resampling."""
    value: float
    ci_lower: float
    ci_upper: float
    metric_name: str
    unit: str = "%"

    def format_display(self) -> str:
        if self.unit == "%":
            return f"{self.value:.1f}% [{self.ci_lower:.1f}%, {self.ci_upper:.1f}%]"
        elif self.unit == "$":
            return f"${self.value:.4f} [${self.ci_lower:.4f}, ${self.ci_upper:.4f}]"
        elif self.unit == "s":
            return f"{self.value:.2f}s [{self.ci_lower:.2f}s, {self.ci_upper:.2f}s]"
        return f"{self.value:.2f} [{self.ci_lower:.2f}, {self.ci_upper:.2f}]"


class BenchmarkReportMetrics(BaseModel):
    """Aggregate benchmark metrics calculated across all instances with confidence intervals."""
    total_instances: int
    detection_precision: MetricWithCI
    detection_recall: MetricWithCI
    localization_hit_at_1: MetricWithCI
    localization_hit_at_3: MetricWithCI
    candidate_brt_rate: MetricWithCI
    plausible_brt_rate: MetricWithCI
    patch_plausible_rate: MetricWithCI
    patch_correct_rate: MetricWithCI
    regression_rate: MetricWithCI
    epr_top_1_precision: MetricWithCI
    avg_duration_seconds: MetricWithCI
    avg_cost_usd_per_bug: MetricWithCI
    failure_taxonomy_distribution: Dict[str, int] = Field(default_factory=dict)
    category_breakdown: Dict[str, Dict[str, float]] = Field(default_factory=dict)
