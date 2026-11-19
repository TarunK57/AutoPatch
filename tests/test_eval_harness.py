"""Unit tests verifying the evaluation harness, 30 seeded bugs, SWE-bench Lite loader,

bootstrap confidence intervals, AutoCodeRover failure taxonomy, and ablations.
"""

import json
import tempfile
from pathlib import Path

import pytest

from eval.ablations.runner import AblationMode, AblationRunner, run_all_ablations
from eval.dataset.models import (
    AutoCodeRoverFailureCategory,
    BugCategory,
    EvaluationInstance,
    InstanceEvaluationResult,
    Language,
)
from eval.dataset.seeded_bugs import SEEDED_BUGS, get_seeded_dataset
from eval.dataset.swe_bench_loader import infer_category_from_text, load_swe_bench_dataset
from eval.metrics.engine import EvaluationMetricsEngine, compute_bootstrap_ci
from eval.metrics.failure_taxonomy import FailureTaxonomyClassifier
from eval.reporter.markdown_reporter import MarkdownReporter
from eval.runner import run_evaluation_benchmark


def test_seeded_dataset_contains_30_bugs_across_all_categories_and_languages():
    """Verifies dataset size, category distribution (all 7 categories), and language coverage."""
    dataset = get_seeded_dataset()
    assert len(dataset) == 30

    # Verify both Python and JavaScript are represented
    python_bugs = [b for b in dataset if b.language == Language.PYTHON]
    js_bugs = [b for b in dataset if b.language == Language.JAVASCRIPT]
    assert len(python_bugs) >= 15
    assert len(js_bugs) >= 10

    # Verify all 7 required defect categories are present
    categories = {b.category for b in dataset}
    assert BugCategory.OFF_BY_ONE in categories
    assert BugCategory.VALIDATION in categories
    assert BugCategory.NULL_ACCESS in categories
    assert BugCategory.SECURITY in categories
    assert BugCategory.CONCURRENCY_LITE in categories
    assert BugCategory.WRONG_OPERATOR in categories
    assert BugCategory.BOUNDARY in categories

    # Verify every bug has required execution anchors
    for b in dataset:
        assert b.instance_id
        assert b.buggy_code
        assert b.ground_truth_patch
        assert b.ground_truth_code
        assert b.hidden_oracle_test
        assert b.file_path


def test_swe_bench_loader_parses_instances_and_infers_categories():
    """Verifies that the SWE-bench Lite loader parses standard JSON format and infers categories."""
    fixture_path = Path("eval/dataset/fixtures/swe_bench_lite_sample.json")
    instances = load_swe_bench_dataset(fixture_path)

    assert len(instances) == 2
    inst1 = instances[0]
    assert inst1.instance_id == "pytest-dev__pytest-5227"
    assert inst1.language == Language.PYTHON
    assert inst1.source == "swe-bench-lite"
    assert "DEFAULT_LOG_FORMAT" in inst1.ground_truth_patch

    inst2 = instances[1]
    assert inst2.instance_id == "django__django-11099"
    assert inst2.language == Language.PYTHON
    assert inst2.category == BugCategory.VALIDATION

    # Test category inference heuristics
    assert infer_category_from_text("fix off by one fencepost error") == BugCategory.OFF_BY_ONE
    assert infer_category_from_text("SQL injection vulnerability in user lookup") == BugCategory.SECURITY
    assert infer_category_from_text("Null pointer exception TypeError: 'NoneType'") == BugCategory.NULL_ACCESS
    assert infer_category_from_text("Missing await on async promise in loop") == BugCategory.CONCURRENCY_LITE


def test_bootstrap_confidence_interval_computation():
    """Verifies empirical bootstrap resampling and 95% confidence bounds."""
    # Constant values -> CI upper == lower == mean
    vals_const = [100.0, 100.0, 100.0, 100.0]
    mean, lower, upper = compute_bootstrap_ci(vals_const, seed=42)
    assert mean == 100.0
    assert lower == 100.0
    assert upper == 100.0

    # Varied binary rates
    vals_varied = [100.0, 100.0, 100.0, 0.0]
    mean, lower, upper = compute_bootstrap_ci(vals_varied, n_bootstrap=500, seed=42)
    assert mean == 75.0
    assert lower < mean
    assert upper > mean
    assert 0.0 <= lower <= 100.0
    assert 0.0 <= upper <= 100.0

    # Determinism test
    m1, l1, u1 = compute_bootstrap_ci(vals_varied, seed=123)
    m2, l2, u2 = compute_bootstrap_ci(vals_varied, seed=123)
    assert (m1, l1, u1) == (m2, l2, u2)


def test_autocode_rover_failure_taxonomy_classification():
    """Verifies AutoCodeRover failure taxonomy classification logic across all states."""
    # 1. Success case
    success_res = InstanceEvaluationResult(
        instance_id="TEST-1",
        language=Language.PYTHON,
        category=BugCategory.OFF_BY_ONE,
        localized_hit_at_3=True,
        candidate_brt_generated=True,
        plausible_brt_confirmed=True,
        patch_synthesized=True,
        patch_applies_cleanly=True,
        patch_plausible=True,
        patch_correct=True,
        regression_detected=False,
    )
    cat, _ = FailureTaxonomyClassifier.classify(success_res)
    assert cat == AutoCodeRoverFailureCategory.NONE

    # 2. Regression failure
    regr_res = success_res.model_copy(update={"regression_detected": True})
    cat, _ = FailureTaxonomyClassifier.classify(regr_res)
    assert cat == AutoCodeRoverFailureCategory.REGRESSION_FAILURE

    # 3. Wrong location
    wrong_loc_res = success_res.model_copy(update={"localized_hit_at_3": False, "localization_rank": 5})
    cat, _ = FailureTaxonomyClassifier.classify(wrong_loc_res)
    assert cat == AutoCodeRoverFailureCategory.WRONG_LOCATION

    # 4. BRT failure
    brt_fail_res = success_res.model_copy(update={"plausible_brt_confirmed": False})
    cat, _ = FailureTaxonomyClassifier.classify(brt_fail_res)
    assert cat == AutoCodeRoverFailureCategory.BRT_FAILURE

    # 5. No patch
    no_patch_res = success_res.model_copy(update={"patch_synthesized": False})
    cat, _ = FailureTaxonomyClassifier.classify(no_patch_res)
    assert cat == AutoCodeRoverFailureCategory.NO_PATCH

    # 6. Wrong patch (oracle failed)
    wrong_patch_res = success_res.model_copy(update={"patch_plausible": False})
    cat, _ = FailureTaxonomyClassifier.classify(wrong_patch_res)
    assert cat == AutoCodeRoverFailureCategory.WRONG_PATCH

    # 7. Overfitted patch
    overfit_res = success_res.model_copy(update={"patch_plausible": True, "patch_correct": False})
    cat, _ = FailureTaxonomyClassifier.classify(overfit_res)
    assert cat == AutoCodeRoverFailureCategory.OVERFITTED_PATCH


def test_ablation_runner_distinguishes_feature_contributions():
    """Verifies that ablations accurately reflect the impact of BRT, SBFL, and Templates."""
    dataset = get_seeded_dataset()[:6]

    # Full mode
    full_runner = AblationRunner(mode=AblationMode.FULL)
    full_results = [full_runner.evaluate_instance(inst) for inst in dataset]
    assert all(r.localized_hit_at_1 for r in full_results)
    assert all(r.candidate_brt_generated for r in full_results)

    # Without BRT
    no_brt_runner = AblationRunner(mode=AblationMode.NO_BRT)
    no_brt_results = [no_brt_runner.evaluate_instance(inst) for inst in dataset]
    assert all(not r.candidate_brt_generated for r in no_brt_results)

    # Without SBFL
    no_sbfl_runner = AblationRunner(mode=AblationMode.NO_SBFL)
    no_sbfl_results = [no_sbfl_runner.evaluate_instance(inst) for inst in dataset]
    # Localization drops without multi-strata SBFL
    assert sum(1 for r in no_sbfl_results if r.localized_hit_at_1) < len(dataset)

    # Templates only ($0 LLM spend)
    templ_runner = AblationRunner(mode=AblationMode.TEMPLATES_ONLY)
    templ_results = [templ_runner.evaluate_instance(inst) for inst in dataset]
    assert all(r.cost_usd == 0.0 for r in templ_results)


def test_single_command_evaluation_runner_generates_report_and_json():
    """Acceptance criterion: Single command writes eval/report.md plus JSON file with reproducible results."""
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td)
        dataset = get_seeded_dataset()[:5]

        # Run 1
        res1 = run_evaluation_benchmark(
            dataset=dataset,
            output_dir=out_dir,
            seed=42,
            runs=2,
            include_ablations=True,
        )

        md_path = res1["report_markdown"]
        json_path = res1["results_json"]

        assert md_path.is_file()
        assert json_path.is_file()

        # Check Markdown content
        md_text = md_path.read_text(encoding="utf-8")
        assert "# AutoPatch Empirical Benchmark Evaluation Report" in md_text
        assert "95% Bootstrap CI" in md_text
        assert "Failure Analysis (AutoCodeRover Taxonomy)" in md_text
        assert "Ablation Study: Which Features Matter?" in md_text

        # Check JSON content
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert "summary_metrics" in data
        assert "failure_taxonomy" in data
        assert "ablations" in data
        assert data["metadata"]["seed"] == 42
        assert data["metadata"]["total_instances"] == 10  # 5 instances * 2 runs

        # Reproducibility check with same seed
        res2 = run_evaluation_benchmark(
            dataset=dataset,
            output_dir=out_dir,
            seed=42,
            runs=2,
            include_ablations=True,
        )
        assert res1["metrics"].patch_plausible_rate.value == res2["metrics"].patch_plausible_rate.value
