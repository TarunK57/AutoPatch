"""Unit tests for clean git-apply execution, retry loop, and plain-language root cause rationale."""

import subprocess
from pathlib import Path
import pytest
from autopatch.locator.models import BuggyLocation, RootCause
from autopatch.patcher.agent import PatcherAgent


@pytest.fixture
def git_repo_workspace(tmp_path: Path):
    """Initializes a git repository with a source file to verify git-apply compatibility."""
    repo_dir = tmp_path / "git_patch_repo"
    repo_dir.mkdir()

    # Initialize real git repo
    subprocess.run(["git", "init"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test Engineer"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@autopatch.io"], cwd=str(repo_dir), check=True)

    # Initial file
    source_content = """class BillingEngine:
    def compute(self, subtotal: float, discount: float) -> float:
        rate = discount / 100.0
        return subtotal * (1.0 - rate)
"""
    (repo_dir / "billing.py").write_text(source_content)
    subprocess.run(["git", "add", "billing.py"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_dir), check=True)

    root_cause = RootCause(
        summary="compute does not guard against discount > 100.0",
        trigger_input_or_state="discount=150.0",
        causal_chain=["Caller supplies invalid discount", "compute produces negative billing output"],
        buggy_locations=[
            BuggyLocation(
                file="billing.py",
                class_name="BillingEngine",
                method_name="compute",
                line_start=2,
                line_end=4,
                score=0.95,
                rationale="Missing upper bound guard on discount percentage",
            )
        ],
        confidence=0.95,
        strata_used=2,
        total_tokens_used=350,
    )

    return repo_dir, root_cause


def test_every_patch_applies_cleanly_with_git_apply(git_repo_workspace):
    """Acceptance criteria:
    - Every patch applies cleanly with git apply
    - Each has a plain-language explanation tied to the root cause
    """
    repo_dir, root_cause = git_repo_workspace

    # Mock LLM generating valid patch in required tag format
    def valid_patch_llm(prompt: str) -> str:
        return """<file>billing.py</file>
<original>
        rate = discount / 100.0
        return subtotal * (1.0 - rate)
</original>
<patched>
        clamped_discount = min(100.0, max(0.0, discount))
        rate = clamped_discount / 100.0
        return subtotal * (1.0 - rate)
</patched>
Rationale: Clamps discount percentage between 0 and 100 to prevent negative invoice totals when excessive discounts are provided.
Risk Notes: Does not alter public method signature.
"""

    agent = PatcherAgent(project_root=repo_dir, llm_client=valid_patch_llm)
    result = agent.generate_candidate_patches(root_cause=root_cause, max_candidates=1)

    assert len(result.candidate_patches) == 1
    patch = result.candidate_patches[0]

    # Verify plain-language explanation tied to root cause
    assert len(patch.rationale) > 20
    assert "discount" in patch.rationale.lower()

    # Verify unified diff format
    assert patch.unified_diff.startswith("--- a/billing.py\n+++ b/billing.py\n")

    # Test clean git apply
    cmd = ["git", "apply", "--check", "-"]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_dir),
        input=patch.unified_diff,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"git apply failed: {proc.stderr}"


def test_patcher_retry_loop_recovers_from_mismatched_original_text(git_repo_workspace):
    """Acceptance criterion: Retry loop (max 3): if original text does not match, feed exact error back and regenerate."""
    repo_dir, root_cause = git_repo_workspace

    call_count = 0

    def retry_recovering_llm(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First attempt: hallucinated original text that doesn't exist in file
            return """<file>billing.py</file>
<original>
        completely_wrong_line_that_does_not_exist = 42
</original>
<patched>
        rate = 0.0
</patched>
Rationale: Bad patch first attempt.
"""
        else:
            # Second attempt: verifies feedback error and provides exact matching original snippet
            assert "Original snippet does not match exact content" in prompt
            return """<file>billing.py</file>
<original>
        rate = discount / 100.0
        return subtotal * (1.0 - rate)
</original>
<patched>
        rate = min(100.0, discount) / 100.0
        return subtotal * (1.0 - rate)
</patched>
Rationale: Bounded discount percentage to 100.
"""

    agent = PatcherAgent(project_root=repo_dir, llm_client=retry_recovering_llm, max_retries=3)
    result = agent.generate_candidate_patches(root_cause=root_cause, max_candidates=1)

    # Invariant: Recovered on retry 1
    assert result.retry_count == 1
    assert len(result.candidate_patches) == 1
    assert result.candidate_patches[0].applies_cleanly is True
    assert "min(100.0, discount)" in result.candidate_patches[0].patched_snippet
