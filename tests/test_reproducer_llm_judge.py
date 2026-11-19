"""Unit tests for the LLM Judge validating failure trace relevance."""

import pytest
from autopatch.detection.models import Finding, FindingCategory
from autopatch.locator.models import RootCause
from autopatch.reproducer.judge import BRTJudge


def test_judge_rejects_unrelated_environment_and_import_errors():
    """Acceptance criterion: reject tests that fail for unrelated reasons (import errors, environment)."""
    judge = BRTJudge(llm_client=None)

    finding = Finding(
        file="src/billing.py",
        line_start=10,
        line_end=12,
        symbol="calculate_tax",
        category=FindingCategory.LOGIC_ERROR,
        evidence="return total / 0",
        detector="AST_RULE",
        raw_confidence=0.9,
        description="Division by zero",
    )

    # 1. ModuleNotFoundError must be rejected immediately
    res1 = judge.evaluate_failure(
        finding=finding,
        root_cause=None,
        test_code="import pytest",
        failure_trace="ModuleNotFoundError: No module named 'fake_lib'",
        error_type="ModuleNotFoundError",
    )
    assert res1["confirmed"] is False
    assert "environment/syntax error" in res1["reasoning"]

    # 2. SyntaxError must be rejected immediately
    res2 = judge.evaluate_failure(
        finding=finding,
        root_cause=None,
        test_code="def broken(",
        failure_trace="SyntaxError: invalid syntax",
        error_type="SyntaxError",
    )
    assert res2["confirmed"] is False


def test_judge_confirms_valid_bug_reproduction_failure():
    """Acceptance criterion: an LLM judge confirms that the failure is caused by the reported bug."""
    finding = Finding(
        file="src/auth.py",
        line_start=20,
        line_end=22,
        symbol="check_token",
        category=FindingCategory.SECURITY,
        cwe="CWE-287",
        evidence="assert token == 'valid'",
        detector="SECURITY_CWE",
        raw_confidence=0.95,
        description="Token verification failure on null claims",
    )

    root_cause = RootCause(
        summary="Token parser assumes non-null user payload",
        trigger_input_or_state="None token passed to check_token",
        causal_chain=["Caller invokes check_token(None)", "AttributeError on None.claims"],
        confidence=0.95,
        strata_used=2,
        total_tokens_used=500,
    )

    def mock_judge_llm(prompt: str) -> str:
        return '{"confirmed": true, "reasoning": "The AttributeError in check_token directly reproduces the unhandled null claims bug identified in the finding."}'

    judge = BRTJudge(llm_client=mock_judge_llm)

    res = judge.evaluate_failure(
        finding=finding,
        root_cause=root_cause,
        test_code="def test_null_token(): check_token(None)",
        failure_trace="AttributeError: 'NoneType' object has no attribute 'claims'",
        error_type="AttributeError",
    )

    assert res["confirmed"] is True
    assert "directly reproduces" in res["reasoning"]
