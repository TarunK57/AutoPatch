"""Core evaluation orchestrator executing benchmark suites, ablations, and report generation."""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from autopatch.core.logging import get_logger
from eval.ablations.runner import AblationMode, AblationRunner, run_all_ablations
from eval.dataset.models import BenchmarkReportMetrics, EvaluationInstance, InstanceEvaluationResult
from eval.dataset.seeded_bugs import get_seeded_dataset
from eval.dataset.diverse_bugs import get_diverse_dataset
from eval.dataset.swe_bench_loader import load_swe_bench_dataset
from eval.metrics.engine import EvaluationMetricsEngine
from eval.reporter.markdown_reporter import MarkdownReporter

logger = get_logger(__name__)


def run_evaluation_benchmark(
    dataset: Optional[List[EvaluationInstance]] = None,
    swe_bench_file: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    seed: int = 42,
    runs: int = 1,
    include_ablations: bool = True,
    include_diverse: bool = False,
    command_executed: Optional[str] = None,
    model_version: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes the comprehensive evaluation benchmark across instances and ablations.

    Args:
        dataset: Explicit list of EvaluationInstances (defaults to the 30 seeded bugs).
        swe_bench_file: Optional path to a SWE-bench Lite JSON/JSONL dataset file.
        output_dir: Directory where report.md and results.json will be saved (defaults to 'eval/').
        seed: Random seed for deterministic reproducibility.
        runs: Number of repeated evaluation runs.
        include_ablations: Whether to run ablation conditions (Full, No-BRT, No-SBFL, Templates, LLM).

    Returns:
        Dictionary containing paths to generated reports and summary metrics.
    """
    # 1. Deterministic seed setup
    random.seed(seed)

    out_dir = output_dir or Path("eval")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 2. Resolve dataset
    instances: List[EvaluationInstance] = []
    dataset_source = "seeded-30"

    if swe_bench_file and Path(swe_bench_file).is_file():
        instances = load_swe_bench_dataset(swe_bench_file)
        dataset_source = f"swe-bench-lite ({Path(swe_bench_file).name})"
    elif dataset is not None:
        instances = dataset
        dataset_source = "custom-dataset"
    else:
        instances = get_seeded_dataset()
        if include_diverse:
            diverse_instances = get_diverse_dataset()
            instances.extend(diverse_instances)
            dataset_source = f"seeded-30 + diverse-{len(diverse_instances)}"
        else:
            dataset_source = "seeded-30"

    logger.info(f"Loaded {len(instances)} instances from {dataset_source}. Running benchmark (seed={seed}, runs={runs})...")

    # 3. Execute Primary Benchmark (Full Pipeline)
    full_runner = AblationRunner(mode=AblationMode.FULL, seed=seed)
    all_run_results: List[InstanceEvaluationResult] = []

    for r_idx in range(runs):
        run_seed = seed + r_idx
        run_runner = AblationRunner(mode=AblationMode.FULL, seed=run_seed)
        for inst in instances:
            res = run_runner.evaluate_instance(inst)
            all_run_results.append(res)

    # Metrics engine with bootstrap CI
    metrics_engine = EvaluationMetricsEngine(seed=seed, n_bootstrap=1000)
    full_metrics = metrics_engine.calculate_metrics(all_run_results)

    # 4. Execute Ablations
    ablation_metrics: Dict[str, BenchmarkReportMetrics] = {}
    if include_ablations:
        logger.info("Executing ablation study (Full, No-BRT, No-SBFL, Templates-Only, LLM-Only)...")
        ablations_raw = run_all_ablations(instances=instances, seed=seed)
        for mode_key, mode_results in ablations_raw.items():
            ab_met = metrics_engine.calculate_metrics(mode_results)
            ablation_metrics[mode_key] = ab_met

    # 5. Generate Reports (Markdown & JSON)
    reporter = MarkdownReporter(output_dir=out_dir)
    # Take representative single-run results for detailed instance breakdown table
    sample_results = all_run_results[:len(instances)]

    md_path, json_path = reporter.generate_report(
        full_metrics=full_metrics,
        full_results=sample_results,
        ablation_metrics=ablation_metrics,
        seed=seed,
        runs=runs,
        dataset_source=dataset_source,
        command_executed=command_executed,
        model_version=model_version,
    )

    logger.info(f"Evaluation benchmark complete! Reports written to:\n - {md_path}\n - {json_path}")

    return {
        "report_markdown": md_path,
        "results_json": json_path,
        "total_instances": len(instances),
        "metrics": full_metrics,
        "ablation_metrics": ablation_metrics,
    }
