"""Unit tests for minimal-diff rules, test-file protection, and signature change detection."""

import pytest
from autopatch.core.exceptions import TestModificationForbiddenError
from autopatch.patcher.diff_utils import validate_minimal_diff_rules
from autopatch.patcher.models import CandidatePatch


def test_patch_rejects_modifying_test_files():
    """Acceptance criterion: no patch modifies test files."""
    forbidden_targets = [
        "tests/test_service.py",
        "src/__tests__/app.test.js",
        "spec/models/order_spec.rb",
        "tests/repro_bug.py",
    ]

    for path in forbidden_targets:
        with pytest.raises(TestModificationForbiddenError):
            CandidatePatch(
                file=path,
                original_snippet="def test_foo(): pass",
                patched_snippet="def test_foo(): assert True",
                rationale="Altering test assertion",
            )


def test_reject_whitespace_only_noise():
    """Verify rejection of whitespace-only edits without semantic modification."""
    orig = "def calculate(x):\n    return x + 1"
    # Same content with modified trailing spaces/indent
    patched = "def calculate(x):\n        return x + 1"

    is_valid, violations, _ = validate_minimal_diff_rules(orig, patched, "src/calc.py")
    assert is_valid is False
    assert any("whitespace-only" in v for v in violations)


def test_reject_deletion_of_assertions():
    """Verify rejection of edits that delete existing assertions."""
    orig = "assert user.is_authenticated\nreturn user.profile"
    patched = "return user.profile"

    is_valid, violations, _ = validate_minimal_diff_rules(orig, patched, "src/auth.py")
    assert is_valid is False
    assert any("deletion of existing assertions" in v for v in violations)


def test_detect_and_flag_public_signature_changes():
    """Verify that public function signature modifications are explicitly flagged."""
    orig = "def process_payment(amount: float):"
    patched = "def process_payment(amount: float, currency: str = 'USD'):"

    is_valid, violations, flags_sig = validate_minimal_diff_rules(orig, patched, "src/pay.py")
    assert is_valid is True
    assert flags_sig is True  # Successfully flagged public signature adjustment
