"""Failure analysis taxonomy modeled after AutoCodeRover.

Classifies unverified or incorrect patch attempts into actionable categories:
- Wrong Location: Localization failed to identify the buggy method or file.
- No Patch: Patch generation produced no applicable or valid patch candidates.
- Wrong Patch: Synthesized patch applies cleanly but fails the hidden oracle test.
- Overfitted Patch: Patch special-cases test values or fails generalized boundary checks.
- Regression Failure: Patch passes the bug reproduction test but breaks existing tests.
- BRT Failure: Reproducer failed to construct a valid fail-to-pass reproduction test.
- None (Fixed): Bug successfully located, reproduced, patched, and verified.
"""

from __future__ import annotations

from typing import Dict, List, Tuple
from eval.dataset.models import AutoCodeRoverFailureCategory, InstanceEvaluationResult


class FailureTaxonomyClassifier:
    """Classifies evaluation instances into AutoCodeRover failure categories."""

    @staticmethod
    def classify(result: InstanceEvaluationResult) -> Tuple[AutoCodeRoverFailureCategory, str]:
        """Determines the primary failure category and explanatory reason for an evaluation result."""
        # 1. Wrong location
        if not result.localized_hit_at_3:
            return (
                AutoCodeRoverFailureCategory.WRONG_LOCATION,
                f"Buggy method not found in top-3 suspicious locations (rank={result.localization_rank}).",
            )

        # 2. BRT failure
        if not result.candidate_brt_generated or not result.plausible_brt_confirmed:
            return (
                AutoCodeRoverFailureCategory.BRT_FAILURE,
                "Reproducer agent failed to construct a confirmed Fail-to-Pass BRT.",
            )

        # 3. No patch
        if not result.patch_synthesized or not result.patch_applies_cleanly:
            return (
                AutoCodeRoverFailureCategory.NO_PATCH,
                "Patcher agent was unable to synthesize a clean, applicable candidate patch.",
            )

        # 4. Regression failure
        if result.regression_detected:
            return (
                AutoCodeRoverFailureCategory.REGRESSION_FAILURE,
                "Patch resolved targeted bug but introduced regressions into existing test suite.",
            )

        # 5. Overfitted patch
        if result.patch_plausible and not result.patch_correct:
            return (
                AutoCodeRoverFailureCategory.OVERFITTED_PATCH,
                "Candidate patch passed local checks but failed semantic equivalence / general specification.",
            )

        # 6. Wrong patch
        if not result.patch_plausible:
            return (
                AutoCodeRoverFailureCategory.WRONG_PATCH,
                "Candidate patch applied cleanly but failed the hidden oracle test.",
            )

        # 7. Success case
        if result.patch_plausible and result.patch_correct:
            return AutoCodeRoverFailureCategory.NONE, "Bug resolved and verified against oracle tests."

        return AutoCodeRoverFailureCategory.NONE, "Resolved."

    @staticmethod
    def summarize_distribution(results: List[InstanceEvaluationResult]) -> Dict[str, int]:
        """Summarizes failure counts across all evaluation results."""
        counts = {cat.value: 0 for cat in AutoCodeRoverFailureCategory}
        for r in results:
            cat, reason = FailureTaxonomyClassifier.classify(r)
            r.failure_category = cat
            r.failure_reason = reason
            counts[cat.value] += 1
        return counts
