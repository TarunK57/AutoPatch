"""Overfitting guard detecting special-casing and narrow test-tailored patches.

Combines AST literal matching against reproduction test code with semantic LLM review.
"""

import json
import re
from typing import Callable, List, Optional, Set
from autopatch.patcher.models import CandidatePatch
from autopatch.security.redaction import assert_clean_prompt, redact_secrets
from autopatch.verifier.models import OverfittingCheckResult


class OverfittingGuard:
    """Detects patches that special-case test inputs or fix only the isolated reported example."""

    def __init__(self, llm_client: Optional[Callable[[str], str]] = None):
        self.llm_client = llm_client

    def inspect_patch(
        self,
        patch: CandidatePatch,
        brt_test_code: Optional[str] = None,
    ) -> OverfittingCheckResult:
        """Executes static and semantic overfitting analysis."""
        static_flags: List[str] = []

        # 1. Static check: compare literals in patch against test code
        if brt_test_code:
            test_literals = self._extract_literals(brt_test_code)
            patch_text = patch.patched_snippet

            # Look for special casing constructs: if x == <literal>, case <literal>, switch
            for lit in test_literals:
                # Check if literal appears in a conditional guard in patch
                cond_pattern = rf"(?:if|elif|case)\s+[^:]*?==\s*{re.escape(lit)}\b"
                if re.search(cond_pattern, patch_text):
                    static_flags.append(
                        f"Patch conditionally hardcodes test value '{lit}', indicating narrow special-casing."
                    )

        # 2. Semantic LLM review (if LLM client provided)
        llm_notes: Optional[str] = None
        is_overfit = len(static_flags) > 0

        if self.llm_client and brt_test_code:
            llm_decision = self._llm_overfitting_review(patch, brt_test_code)
            if llm_decision.get("is_overfit", False):
                is_overfit = True
                llm_notes = llm_decision.get("reasoning", "Semantic review identified overfitting.")

        penalty = 0.35 if is_overfit else 0.0

        return OverfittingCheckResult(
            is_overfit=is_overfit,
            static_flags=static_flags,
            llm_review_notes=llm_notes,
            confidence_penalty=penalty,
        )

    def _extract_literals(self, code: str) -> Set[str]:
        """Extracts candidate test literals (strings > 3 chars and non-trivial numbers)."""
        literals: Set[str] = set()

        # Strings
        str_matches = re.findall(r"['\"]([a-zA-Z0-9_-]{4,})['\"]", code)
        literals.update(f"'{s}'" for s in str_matches)
        literals.update(f'"{s}"' for s in str_matches)

        # Non-trivial numbers (exclude 0, 1, -1)
        num_matches = re.findall(r"\b(\d{2,})\b", code)
        literals.update(num_matches)

        return literals

    def _llm_overfitting_review(self, patch: CandidatePatch, brt_code: str) -> dict:
        prompt = (
            "You are an expert patch review auditor.\n"
            "Assess whether the candidate patch below is a general, principled fix or if it OVERFITS by special-casing test inputs.\n\n"
            f"--- REPRODUCTION TEST ---\n{brt_code}\n\n"
            f"--- CANDIDATE PATCH ---\n{patch.unified_diff or patch.patched_snippet}\n\n"
            "Return JSON:\n"
            '{"is_overfit": true or false, "reasoning": "Detailed justification"}\n'
        )
        sanitized_prompt, _ = redact_secrets(prompt)
        assert_clean_prompt(sanitized_prompt)

        raw = self.llm_client(sanitized_prompt)
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1:
                return json.loads(raw[start : end + 1])
        except Exception:
            pass
        return {"is_overfit": False}
