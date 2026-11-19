"""Evaluation dataset package providing seeded bugs and SWE-bench Lite instance loaders."""

from eval.dataset.models import (
    AutoCodeRoverFailureCategory,
    BenchmarkReportMetrics,
    BugCategory,
    EvaluationInstance,
    InstanceEvaluationResult,
    Language,
    MetricWithCI,
)
from eval.dataset.seeded_bugs import SEEDED_BUGS, get_seeded_dataset
from eval.dataset.swe_bench_loader import load_swe_bench_dataset

__all__ = [
    "BugCategory",
    "Language",
    "EvaluationInstance",
    "AutoCodeRoverFailureCategory",
    "InstanceEvaluationResult",
    "MetricWithCI",
    "BenchmarkReportMetrics",
    "SEEDED_BUGS",
    "get_seeded_dataset",
    "load_swe_bench_dataset",
]
