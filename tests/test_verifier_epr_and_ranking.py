"""Unit tests verifying Ensemble Pass Rate (EPR) calculation, candidate ranking, and selection modes.

Acceptance Criteria:
- Ensemble Pass Rate correctly calculates the percentage of candidate BRTs passing on a patch.
- Candidate patches are ranked primarily by EPR descending, then secondary by verification status, and tertiary by diff size ascending.
- Top-K (K=1 for precision, K=3 for balance) and Threshold selection modes operate correctly.
- EPR, ranks, diff sizes, and evaluation notes are stored and exposed in EnsembleEvaluation.
"""

import tempfile
from pathlib import Path
from uuid import uuid4

from autopatch.patcher.models import CandidatePatch
from autopatch.verifier.engine import VerifierEngine
from autopatch.verifier.models import VerificationStatus


def test_ensemble_pass_rate_and_ranking_by_epr_and_diff_size():
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        src_dir = proj / "src"
        src_dir.mkdir()
        test_dir = proj / "tests"
        test_dir.mkdir()

        # Buggy scoring function with multiple unhandled edge cases
        score_file = src_dir / "scorer.py"
        score_file.write_text(
            """def calculate_score(val):
    return val * 10
"""
        )

        existing_test = test_dir / "test_scorer_existing.py"
        existing_test.write_text(
            """from src.scorer import calculate_score

def test_positive_scale():
    assert calculate_score(5) == 50
"""
        )

        # 4 distinct BRTs covering edge-case inputs
        brts = {
            "tests/test_brt_none.py": (
                "from src.scorer import calculate_score\n"
                "def test_none_input(): assert calculate_score(None) == 0\n"
            ),
            "tests/test_brt_neg.py": (
                "from src.scorer import calculate_score\n"
                "def test_neg_input(): assert calculate_score(-5) == 0\n"
            ),
            "tests/test_brt_over.py": (
                "from src.scorer import calculate_score\n"
                "def test_over_input(): assert calculate_score(15) == 100\n"
            ),
            "tests/test_brt_zero.py": (
                "from src.scorer import calculate_score\n"
                "def test_zero_input(): assert calculate_score(0) == 0\n"
            ),
        }

        # Patch A: Complete fix, but slightly verbose (10 lines diff)
        patch_a_id = uuid4()
        patch_a = CandidatePatch(
            id=patch_a_id,
            file="src/scorer.py",
            original_snippet="def calculate_score(val):\n    return val * 10",
            patched_snippet=(
                "def calculate_score(val):\n"
                "    if val is None or val < 0:\n"
                "        return 0\n"
                "    scaled = val * 10\n"
                "    if scaled > 100:\n"
                "        return 100\n"
                "    return scaled"
            ),
            rationale="Verbose complete fix handling None, negative, and ceiling clamp",
            lines_added=7,
            lines_deleted=2,
            ast_node_delta=15,
        )

        # Patch B: Minimal clean complete fix (smaller diff size than Patch A)
        patch_b_id = uuid4()
        patch_b = CandidatePatch(
            id=patch_b_id,
            file="src/scorer.py",
            original_snippet="def calculate_score(val):\n    return val * 10",
            patched_snippet=(
                "def calculate_score(val):\n"
                "    if not val or val < 0: return 0\n"
                "    return min(100, val * 10)"
            ),
            rationale="Concise minimal fix using min() and truthiness checks",
            lines_added=3,
            lines_deleted=2,
            ast_node_delta=5,
        )

        # Patch C: Partial fix - only handles None, fails negative and over 100
        patch_c_id = uuid4()
        patch_c = CandidatePatch(
            id=patch_c_id,
            file="src/scorer.py",
            original_snippet="def calculate_score(val):\n    return val * 10",
            patched_snippet=(
                "def calculate_score(val):\n"
                "    if val is None: return 0\n"
                "    return val * 10"
            ),
            rationale="Partial fix handling only None",
            lines_added=3,
            lines_deleted=2,
            ast_node_delta=4,
        )

        engine = VerifierEngine(flakiness_runs=1)
        evaluation = engine.verify_candidate_patches(
            project_root=proj,
            candidate_patches=[patch_a, patch_b, patch_c],
            brt_test_paths=list(brts.keys()),
            brt_contents=brts,
            existing_test_command="pytest tests/test_scorer_existing.py",
            selection_mode="TOP_K",
            top_k=1,
        )

        assert len(evaluation.candidate_rankings) == 3

        # Check EPR scores
        res_map = {r.patch_id: r for r in evaluation.candidate_rankings}
        res_a = res_map[str(patch_a_id)]
        res_b = res_map[str(patch_b_id)]
        res_c = res_map[str(patch_c_id)]

        # Patch A and B pass all 4 BRTs -> 100% EPR
        assert res_a.ensemble_pass_rate == 100.0
        assert res_b.ensemble_pass_rate == 100.0

        # Patch C passes test_brt_none and test_brt_zero (2 out of 4) -> 50% EPR
        assert res_c.ensemble_pass_rate == 50.0

        # Check Rankings:
        # Patch B and Patch A both have 100% EPR and VERIFIED status,
        # but Patch B has a smaller diff_size (8 vs 24). Patch B must be Rank 1!
        assert res_b.diff_size < res_a.diff_size
        assert res_b.rank == 1
        assert res_a.rank == 2
        assert res_c.rank == 3

        # Selected patch under top_k=1 must be Patch B
        assert evaluation.selected_patch is not None
        assert evaluation.selected_patch.patch_id == str(patch_b_id)


def test_selection_modes_top_k_and_threshold():
    """Validates top-k and threshold selection logic."""
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        src_dir = proj / "src"
        src_dir.mkdir()
        (src_dir / "helper.py").write_text("def ping(): return 'pong'\n")

        # Fake candidate patches with predetermined diff sizes
        p1 = CandidatePatch(
            id=uuid4(),
            file="src/helper.py",
            original_snippet="def ping(): return 'pong'",
            patched_snippet="def ping():\n    return 'pong'",
            rationale="Passes with full marks",
            lines_added=2,
            lines_deleted=1,
            ast_node_delta=2,
        )
        p2 = CandidatePatch(
            id=uuid4(),
            file="src/helper.py",
            original_snippet="def ping(): return 'pong'",
            patched_snippet="def ping():\n    # fix\n    return 'pong'",
            rationale="Alternative pass",
            lines_added=3,
            lines_deleted=1,
            ast_node_delta=6,
        )

        test_code = "from src.helper import ping\ndef test_p(): assert ping() == 'pong'\n"

        engine = VerifierEngine(flakiness_runs=1)

        # 1. Test THRESHOLD mode
        eval_thresh = engine.verify_candidate_patches(
            project_root=proj,
            candidate_patches=[p1, p2],
            brt_test_paths=["tests/test_brt.py"],
            brt_contents={"tests/test_brt.py": test_code},
            existing_test_command="pytest tests/test_brt.py",
            selection_mode="THRESHOLD",
            epr_threshold=90.0,
        )
        assert eval_thresh.selected_patch is not None
        assert eval_thresh.selected_patch.ensemble_pass_rate >= 90.0

        # 2. Test TOP_K mode with K=3
        eval_top3 = engine.verify_candidate_patches(
            project_root=proj,
            candidate_patches=[p1, p2],
            brt_test_paths=["tests/test_brt.py"],
            brt_contents={"tests/test_brt.py": test_code},
            existing_test_command="pytest tests/test_brt.py",
            selection_mode="TOP_K",
            top_k=3,
        )
        assert eval_top3.selected_patch is not None
        assert eval_top3.top_k == 3
        assert "Selection mode: TOP_K" in eval_top3.evaluation_notes
