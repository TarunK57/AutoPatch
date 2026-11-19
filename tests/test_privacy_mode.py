from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from autopatch.detection.llm_reviewer import LLMSemanticReviewer
from autopatch.detection.models import Finding, FindingCategory
from autopatch.locator.models import BuggyLocation, RootCause
from autopatch.patcher.agent import PatcherAgent
from autopatch.patcher.templates import DeterministicTemplatePatcher
from autopatch.security.privacy_mode import PrivacyGuard, PrivacyModeViolationError


def test_privacy_mode_blocks_external_llm_calls():
    """
    Verify that when Privacy Mode is active:
    - Attempting an LLM call raises PrivacyModeViolationError.
    - LLMSemanticReviewer skips external calls.
    - PatcherAgent relies exclusively on deterministic templates without LLM calls.
    """
    PrivacyGuard.set_global_privacy_mode(True)

    try:
        # 1. Direct LLM assertion check
        with pytest.raises(PrivacyModeViolationError) as exc_info:
            PrivacyGuard.assert_llm_allowed(caller="LocatorLLMClient")
        assert "Privacy Mode is active" in str(exc_info.value)

        # 2. LLMSemanticReviewer skips external calls
        llm_called = []
        reviewer = LLMSemanticReviewer(llm_client=lambda p: llm_called.append(p) or "[]")
        findings = reviewer.detect(Path("/tmp"), [])
        assert len(findings) == 0
        assert len(llm_called) == 0, "Zero LLM calls must be made in Privacy Mode"

        # 3. PatcherAgent uses deterministic templates and skips LLM
        with tempfile.TemporaryDirectory() as tmp_dir:
            proj_root = Path(tmp_dir)
            target_file = proj_root / "calc.py"
            # Bug: Zero division
            target_file.write_text(
                "def avg(items):\n"
                "    return sum(items) / len(items)\n",
                encoding="utf-8",
            )

            root_cause = RootCause(
                summary="Division by zero when items is empty",
                trigger_input_or_state="items = []",
                causal_chain=["calc.py:2"],
                buggy_locations=[
                    BuggyLocation(file="calc.py", method_name="avg", line_start=1, line_end=2)
                ],
                confidence=0.95,
            )

            patcher_llm_called = []
            patcher = PatcherAgent(
                project_root=proj_root,
                llm_client=lambda p: patcher_llm_called.append(p) or "",
                template_patcher=DeterministicTemplatePatcher(),
            )

            result = patcher.generate_candidate_patches(root_cause=root_cause)

            # Invariant: Template generated patch without calling external LLM
            assert len(result.candidate_patches) >= 1
            assert "0.0" in result.candidate_patches[0].patched_snippet
            assert len(patcher_llm_called) == 0, "Patcher must not invoke LLM in Privacy Mode"

    finally:
        # Reset Privacy Mode
        PrivacyGuard.set_global_privacy_mode(False)
        assert PrivacyGuard.is_privacy_mode_active() is False
