"""Metrics calculation engine with 95% bootstrap confidence intervals."""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Tuple

from eval.dataset.models import (
    BenchmarkReportMetrics,
    BugCategory,
    InstanceEvaluationResult,
    MetricWithCI,
)
from eval.metrics.failure_taxonomy import FailureTaxonomyClassifier


def compute_bootstrap_ci(
    values: List[float],
    n_bootstrap: int = 1000,
    ci_level: float = 0.95,
    seed: int = 42,
) -> Tuple[float, float, float]:
    """
    Computes empirical mean and 95% bootstrap confidence intervals [ci_lower, ci_upper].
    Uses pure standard library random sampling for zero external dependencies and deterministic seeds.
    """
    if not values:
        return 0.0, 0.0, 0.0

    mean_val = sum(values) / len(values)
    if len(values) == 1:
        return mean_val, mean_val, mean_val

    rng = random.Random(seed)
    n = len(values)
    bootstrap_means: List[float] = []

    for _ in range(n_bootstrap):
        sample = rng.choices(values, k=n)
        bootstrap_means.append(sum(sample) / n)

    bootstrap_means.sort()
    alpha = (1.0 - ci_level) / 2.0
    lower_idx = max(0, min(n_bootstrap - 1, int(math.floor(alpha * n_bootstrap))))
    upper_idx = max(0, min(n_bootstrap - 1, int(math.ceil((1.0 - alpha) * n_bootstrap) - 1)))

    lower = bootstrap_means[lower_idx]
    upper = bootstrap_means[upper_idx]

    return mean_val, lower, upper

    return mean_val, lower, upper


class EvaluationMetricsEngine:
    """Calculates all benchmark evaluation metrics with 95% bootstrap confidence intervals."""

    def __init__(self, seed: int = 42, n_bootstrap: int = 1000) -> None:
        self.seed = seed
        self.n_bootstrap = n_bootstrap

    def calculate_metrics(
        self,
        results: List[InstanceEvaluationResult],
    ) -> BenchmarkReportMetrics:
        """Calculates comprehensive evaluation metrics, confidence intervals, and taxonomy breakdowns."""
        total = len(results)
        if total == 0:
            raise ValueError("No evaluation results provided for metrics calculation.")

        # Classify failures
        taxonomy_dist = FailureTaxonomyClassifier.summarize_distribution(results)

        # 1. Extraction of metric vectors (0.0 or 100.0 for percentages)
        detected_vals = [100.0 if r.detected else 0.0 for r in results]
        loc1_vals = [100.0 if r.localized_hit_at_1 else 0.0 for r in results]
        loc3_vals = [100.0 if r.localized_hit_at_3 else 0.0 for r in results]
        cand_brt_vals = [100.0 if r.candidate_brt_generated else 0.0 for r in results]
        plaus_brt_vals = [100.0 if r.plausible_brt_confirmed else 0.0 for r in results]
        patch_plaus_vals = [100.0 if r.patch_plausible else 0.0 for r in results]
        patch_corr_vals = [100.0 if r.patch_correct else 0.0 for r in results]
        regression_vals = [100.0 if r.regression_detected else 0.0 for r in results]
        epr_vals = [100.0 if r.epr_top_1_precision else 0.0 for r in results]

        # Timing and cost for resolved bugs
        fixed_results = [r for r in results if r.patch_plausible and r.patch_correct]
        durations = [r.duration_seconds for r in (fixed_results if fixed_results else results)]
        costs = [r.cost_usd for r in (fixed_results if fixed_results else results)]

        # 2. Compute bootstrap confidence intervals
        def _build_ci(vals: List[float], name: str, unit: str = "%") -> MetricWithCI:
            mean_val, lower, upper = compute_bootstrap_ci(vals, n_bootstrap=self.n_bootstrap, seed=self.seed)
            return MetricWithCI(
                value=round(mean_val, 2),
                ci_lower=round(lower, 2),
                ci_upper=round(upper, 2),
                metric_name=name,
                unit=unit,
            )

        det_prec = _build_ci(detected_vals, "Detection Precision")
        det_rec = _build_ci(detected_vals, "Detection Recall")
        hit1 = _build_ci(loc1_vals, "Localization Hit@1")
        hit3 = _build_ci(loc3_vals, "Localization Hit@3")
        c_brt = _build_ci(cand_brt_vals, "Candidate BRT Rate")
        p_brt = _build_ci(plaus_brt_vals, "Plausible BRT Rate")
        p_plaus = _build_ci(patch_plaus_vals, "Patch Plausible Rate")
        p_corr = _build_ci(patch_corr_vals, "Patch Correct Rate")
        regr = _build_ci(regression_vals, "Regression Rate")
        epr = _build_ci(epr_vals, "EPR Top-1 Precision")
        avg_dur = _build_ci(durations, "Average Duration per Fixed Bug", unit="s")
        avg_cost = _build_ci(costs, "Average Cost per Fixed Bug", unit="$")

        # 3. Category Breakdown
        category_breakdown: Dict[str, Dict[str, float]] = {}
        for cat in BugCategory:
            cat_results = [r for r in results if r.category == cat]
            if cat_results:
                n_cat = len(cat_results)
                c_plaus = sum(1 for r in cat_results if r.patch_plausible)
                c_corr = sum(1 for r in cat_results if r.patch_correct)
                c_loc = sum(1 for r in cat_results if r.localized_hit_at_1)
                category_breakdown[cat.value] = {
                    "count": float(n_cat),
                    "localization_hit@1_pct": round(c_loc / n_cat * 100.0, 1),
                    "patch_plausible_pct": round(c_plaus / n_cat * 100.0, 1),
                    "patch_correct_pct": round(c_corr / n_cat * 100.0, 1),
                }

        return BenchmarkReportMetrics(
            total_instances=total,
            detection_precision=det_prec,
            detection_recall=det_rec,
            localization_hit_at_1=hit1,
            localization_hit_at_3=hit3,
            candidate_brt_rate=c_brt,
            plausible_brt_rate=p_brt,
            patch_plausible_rate=p_plaus,
            patch_correct_rate=p_corr,
            regression_rate=regr,
            epr_top_1_precision=epr,
            avg_duration_seconds=avg_dur,
            avg_cost_usd_per_bug=avg_cost,
            failure_taxonomy_distribution=taxonomy_dist,
            category_breakdown=category_breakdown,
        )
