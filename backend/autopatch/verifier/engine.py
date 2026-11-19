"""Verifier Engine executing the 7-step verification pipeline.

Implements:
1. Candidate BRT reproduction verification (must fail on baseline, pass on patch).
2. Existing test suite regression testing (0 regressions tolerated).
3. Lint, type-check, and build validation.
4. Differential invariance checking across untouched public functions.
5. Flakiness stability scoring across 3 repeated executions.
6. Ensemble Pass Rate (EPR) calculation and candidate patch ranking (by EPR, then diff size).
7. Overfitting guard (static AST literal analysis + semantic review).

Verification status classification:
- VERIFIED: All checks pass, 0 regressions, confirmed reproduction, non-overfit.
- PLAUSIBLE_BUT_UNVERIFIED: Passes on patch, 0 regressions, but baseline did not strictly reproduce.
- FAILED: Regressions detected, BRT still fails, or build/syntax errors.
- NEEDS_REVIEW: Overfitting detected, behavior divergence, or test flakiness.
"""

import shutil
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from autopatch.core.exceptions import (
    SandboxSecurityError,
    UnverifiedPatchError,
)
from autopatch.core.logging import get_logger
from autopatch.patcher.diff_utils import verify_patch_applies_cleanly
from autopatch.patcher.models import CandidatePatch
from autopatch.verifier.differential import DifferentialChecker
from autopatch.verifier.models import (
    DifferentialCheckResult,
    EnsembleEvaluation,
    OverfittingCheckResult,
    PatchVerificationResult,
    SingleTestStatus,
    StructuredTestExecutionResult,
    VerificationStatus,
)
from autopatch.verifier.overfitting import OverfittingGuard
from autopatch.verifier.sandbox import EphemeralSandbox, discover_test_command

logger = get_logger(__name__)


class VerifierEngine:
    """Orchestrates comprehensive multi-stage patch verification and candidate ranking."""

    def __init__(
        self,
        sandbox: Optional[EphemeralSandbox] = None,
        differential_checker: Optional[DifferentialChecker] = None,
        overfitting_guard: Optional[OverfittingGuard] = None,
        flakiness_runs: int = 3,
    ):
        self.sandbox = sandbox or EphemeralSandbox()
        self.differential_checker = differential_checker or DifferentialChecker()
        self.overfitting_guard = overfitting_guard or OverfittingGuard()
        self.flakiness_runs = max(1, flakiness_runs)

    def verify_candidate_patches(
        self,
        project_root: Path,
        candidate_patches: List[CandidatePatch],
        brt_test_paths: List[str],
        brt_contents: Optional[Dict[str, str]] = None,
        existing_test_command: str = "pytest",
        build_lint_command: Optional[str] = None,
        selection_mode: str = "TOP_K",
        top_k: int = 1,
        epr_threshold: float = 80.0,
    ) -> EnsembleEvaluation:
        """Executes verification for all candidate patches, computes EPR, and ranks candidates."""
        if not candidate_patches:
            return EnsembleEvaluation(
                candidate_rankings=[],
                selection_mode=selection_mode,
                top_k=top_k,
                selected_patch=None,
                evaluation_notes="No candidate patches provided for verification.",
            )

        root = project_root.resolve()
        test_cmd = existing_test_command
        if test_cmd == "pytest":
            test_cmd = discover_test_command(root)
        verified_results: List[PatchVerificationResult] = []

        # 1. Evaluate baseline test suite and BRT reproduction on unmodified code
        baseline_suite_res, baseline_brt_map = self._evaluate_baseline(
            root=root,
            brt_test_paths=brt_test_paths,
            brt_contents=brt_contents,
            existing_test_command=test_cmd,
        )

        baseline_passing_tests = {
            t.name for t in baseline_suite_res.test_results if t.status == SingleTestStatus.PASSED
        }

        # 2. Verify each candidate patch individually
        for patch in candidate_patches:
            result = self._verify_single_patch(
                root=root,
                patch=patch,
                brt_test_paths=brt_test_paths,
                brt_contents=brt_contents,
                baseline_passing_tests=baseline_passing_tests,
                baseline_brt_map=baseline_brt_map,
                existing_test_command=existing_test_command,
                build_lint_command=build_lint_command,
            )
            verified_results.append(result)

        # 3. Rank candidates: primary by EPR descending, secondary by verification status, tertiary by diff size
        def status_weight(status: VerificationStatus) -> int:
            weights = {
                VerificationStatus.VERIFIED: 4,
                VerificationStatus.NEEDS_REVIEW: 3,
                VerificationStatus.PLAUSIBLE_BUT_UNVERIFIED: 2,
                VerificationStatus.FAILED: 1,
            }
            return weights.get(status, 0)

        verified_results.sort(
            key=lambda r: (
                -r.ensemble_pass_rate,
                -status_weight(r.status),
                r.diff_size,
            )
        )

        # Assign 1-based ranks
        for idx, res in enumerate(verified_results, start=1):
            res.rank = idx

        # 4. Select best candidate patch based on selection mode
        selected = self._select_candidate(
            ranked_results=verified_results,
            selection_mode=selection_mode,
            top_k=top_k,
            epr_threshold=epr_threshold,
        )

        notes = (
            f"Evaluated {len(candidate_patches)} candidate patches. "
            f"Selection mode: {selection_mode} (top_k={top_k}, threshold={epr_threshold}%). "
            f"Selected patch ID: {selected.patch_id if selected else 'None'}."
        )

        return EnsembleEvaluation(
            candidate_rankings=verified_results,
            selection_mode=selection_mode,
            top_k=top_k,
            selected_patch=selected,
            evaluation_notes=notes,
        )

    def _verify_single_patch(
        self,
        root: Path,
        patch: CandidatePatch,
        brt_test_paths: List[str],
        brt_contents: Optional[Dict[str, str]],
        baseline_passing_tests: set,
        baseline_brt_map: Dict[str, bool],
        existing_test_command: str,
        build_lint_command: Optional[str],
    ) -> PatchVerificationResult:
        reasons: List[str] = []
        regressions: List[str] = []

        # Diff size computation: lines added + lines deleted + node delta
        diff_size = patch.lines_added + patch.lines_deleted + (patch.ast_node_delta or 0)

        # Check clean application
        applies_cleanly, apply_err = verify_patch_applies_cleanly(
            project_root=root,
            file_path=patch.file,
            original_snippet=patch.original_snippet,
            patched_snippet=patch.patched_snippet,
        )

        if not applies_cleanly:
            reasons.append(f"Patch does not apply cleanly: {apply_err}")
            return PatchVerificationResult(
                patch_id=str(patch.id),
                status=VerificationStatus.FAILED,
                reasons=reasons,
                diff_size=diff_size,
            )

        # Create temporary patched snapshot
        temp_snapshot_dir = Path(tempfile.mkdtemp(prefix="autopatch_patch_snapshot_"))
        try:
            shutil.copytree(root, temp_snapshot_dir, dirs_exist_ok=True)

            # Apply candidate patch to target file
            target_path = temp_snapshot_dir / patch.file
            content = target_path.read_text(encoding="utf-8", errors="replace")
            patched_content = content.replace(patch.original_snippet, patch.patched_snippet, 1)
            target_path.write_text(patched_content, encoding="utf-8")

            # Stage BRT tests if provided as content
            if brt_contents:
                for rel_path, test_src in brt_contents.items():
                    test_file = temp_snapshot_dir / rel_path
                    test_file.parent.mkdir(parents=True, exist_ok=True)
                    test_file.write_text(test_src, encoding="utf-8")

            # Step 1: Run BRTs on patched snapshot
            brts_passed_count = 0
            all_brt_results: Dict[str, bool] = {}

            for brt_path in brt_test_paths:
                cmd = f"pytest {brt_path}"
                brt_res = self.sandbox.run_tests(temp_snapshot_dir, cmd)
                passed = brt_res.is_success
                all_brt_results[brt_path] = passed
                if passed:
                    brts_passed_count += 1

            total_brts = len(brt_test_paths)
            ensemble_pass_rate = (
                round((brts_passed_count / total_brts) * 100.0, 2) if total_brts > 0 else 0.0
            )

            primary_brt = brt_test_paths[0] if brt_test_paths else ""
            brt_passed_on_patch = all_brt_results.get(primary_brt, False) if primary_brt else False
            brt_failed_on_baseline = baseline_brt_map.get(primary_brt, False)

            if not brt_passed_on_patch:
                reasons.append(f"Reproduction test '{primary_brt}' failed to pass on patched code.")

            if not brt_failed_on_baseline and primary_brt:
                reasons.append(
                    f"Reproduction test '{primary_brt}' did not fail on baseline; bug confirmation unproven."
                )

            # Step 2: Run existing test suite and detect regressions
            patch_suite_res = self.sandbox.run_tests(temp_snapshot_dir, existing_test_command)
            patch_suite_passed = patch_suite_res.is_success

            # Detect regressions: any test that passed on baseline but failed/errored on patch
            for t in patch_suite_res.test_results:
                if t.name in baseline_passing_tests and t.status in {
                    SingleTestStatus.FAILED,
                    SingleTestStatus.ERROR,
                }:
                    regressions.append(t.name)

            if regressions:
                reasons.append(f"Regression detected: {len(regressions)} existing tests broke: {regressions}")

            # Step 3: Lint, type-check, and build
            build_lint_passed = True
            if build_lint_command:
                build_res = self.sandbox.run_tests(temp_snapshot_dir, build_lint_command)
                if not build_res.is_success:
                    build_lint_passed = False
                    reasons.append(f"Build/lint command '{build_lint_command}' failed.")

            # Step 4: Differential check on untouched public functions
            diff_check = self.differential_checker.run_differential_check(
                baseline_snapshot=root,
                patched_snapshot=temp_snapshot_dir,
                affected_files=[patch.file],
            )
            if diff_check.divergent:
                reasons.append(
                    f"Differential check detected divergence in untouched functions: {diff_check.divergent_details}"
                )

            # Step 5: Flakiness stability scoring
            stability_score = 1.0
            if self.flakiness_runs > 1 and primary_brt:
                flaky_trials = 0
                expected_outcome = brt_passed_on_patch
                for _ in range(self.flakiness_runs):
                    rep_res = self.sandbox.run_tests(temp_snapshot_dir, f"pytest {primary_brt}")
                    if rep_res.is_success == expected_outcome:
                        flaky_trials += 1
                stability_score = round(flaky_trials / self.flakiness_runs, 2)
                if stability_score < 1.0:
                    reasons.append(
                        f"Test execution exhibited flakiness: stability score {stability_score} across {self.flakiness_runs} trials."
                    )

            # Step 6 & 7: Overfitting guard inspection
            primary_test_src = ""
            if brt_contents and primary_brt in brt_contents:
                primary_test_src = brt_contents[primary_brt]
            elif (root / primary_brt).is_file():
                primary_test_src = (root / primary_brt).read_text(encoding="utf-8", errors="replace")

            overfit_res = self.overfitting_guard.inspect_patch(
                patch=patch,
                brt_test_code=primary_test_src,
            )
            if overfit_res.is_overfit:
                reasons.append(
                    f"Overfitting guard flagged patch: {overfit_res.static_flags or overfit_res.llm_review_notes}"
                )

            # Determine final verification status
            if regressions or not brt_passed_on_patch or not build_lint_passed:
                status = VerificationStatus.FAILED
            elif overfit_res.is_overfit or diff_check.divergent or stability_score < 0.8:
                status = VerificationStatus.NEEDS_REVIEW
            elif not brt_failed_on_baseline:
                status = VerificationStatus.PLAUSIBLE_BUT_UNVERIFIED
            else:
                status = VerificationStatus.VERIFIED

            return PatchVerificationResult(
                patch_id=str(patch.id),
                status=status,
                reasons=reasons,
                brt_failed_on_baseline=brt_failed_on_baseline,
                brt_passed_on_patch=brt_passed_on_patch,
                baseline_suite_passed=len(baseline_passing_tests) > 0,
                patch_suite_passed=patch_suite_passed and len(regressions) == 0,
                regressions=regressions,
                build_lint_passed=build_lint_passed,
                differential_check=diff_check,
                flakiness_stability_score=stability_score,
                ensemble_pass_rate=ensemble_pass_rate,
                diff_size=diff_size,
                overfitting=overfit_res,
            )

        finally:
            shutil.rmtree(temp_snapshot_dir, ignore_errors=True)

    def _evaluate_baseline(
        self,
        root: Path,
        brt_test_paths: List[str],
        brt_contents: Optional[Dict[str, str]],
        existing_test_command: str,
    ) -> Tuple[StructuredTestExecutionResult, Dict[str, bool]]:
        """Evaluates baseline existing suite and checks that BRTs fail on unmodified code."""
        temp_baseline_dir = Path(tempfile.mkdtemp(prefix="autopatch_baseline_eval_"))
        try:
            shutil.copytree(root, temp_baseline_dir, dirs_exist_ok=True)

            if brt_contents:
                for rel_path, test_src in brt_contents.items():
                    test_file = temp_baseline_dir / rel_path
                    test_file.parent.mkdir(parents=True, exist_ok=True)
                    test_file.write_text(test_src, encoding="utf-8")

            # Run existing test suite
            baseline_suite_res = self.sandbox.run_tests(temp_baseline_dir, existing_test_command)

            # Run each BRT on baseline to confirm reproduction failure
            baseline_brt_map: Dict[str, bool] = {}
            for brt_path in brt_test_paths:
                cmd = f"pytest {brt_path}"
                brt_res = self.sandbox.run_tests(temp_baseline_dir, cmd)
                # Invariant: bug is reproduced ONLY if BRT fails on buggy code
                failed_cleanly = not brt_res.is_success and (brt_res.failed > 0 or brt_res.exit_code != 0)
                baseline_brt_map[brt_path] = failed_cleanly

            return baseline_suite_res, baseline_brt_map

        finally:
            shutil.rmtree(temp_baseline_dir, ignore_errors=True)

    def _select_candidate(
        self,
        ranked_results: List[PatchVerificationResult],
        selection_mode: str,
        top_k: int,
        epr_threshold: float,
    ) -> Optional[PatchVerificationResult]:
        if not ranked_results:
            return None

        if selection_mode == "THRESHOLD":
            # Select first patch meeting EPR threshold, preferring VERIFIED or non-failed
            for res in ranked_results:
                if res.ensemble_pass_rate >= epr_threshold and res.status != VerificationStatus.FAILED:
                    return res
            # Fallback to highest ranked non-failed if none met threshold
            for res in ranked_results:
                if res.status != VerificationStatus.FAILED:
                    return res
            return ranked_results[0]

        # Default "TOP_K"
        candidate_pool = ranked_results[: max(1, top_k)]
        # In candidate pool, prefer VERIFIED
        for res in candidate_pool:
            if res.status == VerificationStatus.VERIFIED:
                return res
        # Next prefer NEEDS_REVIEW or PLAUSIBLE_BUT_UNVERIFIED
        for res in candidate_pool:
            if res.status != VerificationStatus.FAILED:
                return res
        return candidate_pool[0]
