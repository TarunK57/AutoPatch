"""Unit tests for OverfittingGuard (static AST literal analysis + semantic review).

Acceptance Criteria:
- Patches that special-case test literals (e.g. if x == 42) are flagged as overfit.
- LLM semantic review can flag narrow overfitting and apply confidence penalty.
- Clean general fixes pass without overfitting flags.
"""

from uuid import uuid4
from autopatch.patcher.models import CandidatePatch
from autopatch.verifier.models import VerificationStatus
from autopatch.verifier.overfitting import OverfittingGuard


def test_static_literal_overfitting_detection():
    guard = OverfittingGuard()

    # BRT reproduction test code that tests with value 9999 and string 'special_secret'
    test_code = """
def test_boundary_limit():
    assert process_transaction(9999, "special_secret") == True
"""

    # Overfitted patch hardcoding the specific literal 9999
    overfitted_patch = CandidatePatch(
        id=uuid4(),
        file="src/tx.py",
        original_snippet="def process_transaction(val, secret):\n    return False",
        patched_snippet=(
            "def process_transaction(val, secret):\n"
            "    if val == 9999:\n"
            "        return True\n"
            "    return False"
        ),
        rationale="Special cases 9999 to satisfy the test",
        lines_added=4,
        lines_deleted=2,
    )

    res = guard.inspect_patch(patch=overfitted_patch, brt_test_code=test_code)

    assert res.is_overfit is True
    assert len(res.static_flags) > 0
    assert any("9999" in flag for flag in res.static_flags)
    assert res.confidence_penalty > 0.0


def test_semantic_llm_overfitting_review():
    def mock_llm_client(prompt: str) -> str:
        return '{"is_overfit": true, "reasoning": "Patch only fixes the reported test case using an ad-hoc conditional."}'

    guard = OverfittingGuard(llm_client=mock_llm_client)

    test_code = "def test_boundary(): assert check(10) == True\n"
    patch = CandidatePatch(
        id=uuid4(),
        file="src/check.py",
        original_snippet="def check(x): return False",
        patched_snippet="def check(x): return x >= 10",
        rationale="Threshold check",
        lines_added=2,
        lines_deleted=1,
    )

    res = guard.inspect_patch(patch=patch, brt_test_code=test_code)

    assert res.is_overfit is True
    assert res.llm_review_notes == "Patch only fixes the reported test case using an ad-hoc conditional."
    assert res.confidence_penalty == 0.35


def test_clean_general_fix_not_flagged_as_overfit():
    guard = OverfittingGuard()

    test_code = "def test_zero(): assert divide(10, 0) == 0\n"
    general_patch = CandidatePatch(
        id=uuid4(),
        file="src/math.py",
        original_snippet="def divide(a, b):\n    return a / b",
        patched_snippet="def divide(a, b):\n    if b == 0:\n        return 0\n    return a / b",
        rationale="General zero divisor validation guard",
        lines_added=4,
        lines_deleted=2,
    )

    res = guard.inspect_patch(patch=general_patch, brt_test_code=test_code)

    assert res.is_overfit is False
    assert len(res.static_flags) == 0
    assert res.confidence_penalty == 0.0
