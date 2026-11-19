"""Unit tests for finding deduplication and detector agreement confidence boost."""

import pytest
from autopatch.detection.aggregator import deduplicate_and_merge_findings
from autopatch.detection.models import Finding, FindingCategory


def test_duplicates_merged_and_confidence_boosted():
    """Acceptance criterion: duplicates merged; compute raw_confidence from detector agreement."""
    # Finding 1 from AST Rule detector
    f1 = Finding(
        file="src/auth.py",
        line_start=15,
        line_end=17,
        symbol="login",
        category=FindingCategory.LOGIC_ERROR,
        cwe=None,
        evidence="user = authenticate(token)",
        detector="AST_RULE",
        raw_confidence=0.80,
        description="Potential null dereference on unverified token.",
    )

    # Finding 2 from Security detector on overlapping line
    f2 = Finding(
        file="src/auth.py",
        line_start=16,
        line_end=18,
        symbol="login",
        category=FindingCategory.SECURITY,
        cwe="CWE-287",
        evidence="user = authenticate(token); return user.is_admin",
        detector="SECURITY_CWE",
        raw_confidence=0.85,
        description="Improper authentication check leads to privilege escalation.",
    )

    # Unrelated finding in different file
    f3 = Finding(
        file="src/billing.py",
        line_start=5,
        line_end=5,
        symbol="charge",
        category=FindingCategory.INPUT_VALIDATION,
        cwe="CWE-20",
        evidence="def charge(amount):",
        detector="INPUT_VALIDATION",
        raw_confidence=0.75,
        description="Missing range check on billing amount.",
    )

    merged = deduplicate_and_merge_findings([f1, f2, f3])

    # 3 raw findings should collapse into 2 distinct findings
    assert len(merged) == 2

    # Verify merged auth finding
    auth_finding = next(f for f in merged if f.file == "src/auth.py")
    assert auth_finding.category == FindingCategory.SECURITY  # Security prioritized
    assert auth_finding.cwe == "CWE-287"
    assert auth_finding.metadata["merged_count"] == 2
    assert "AST_RULE" in auth_finding.detector
    assert "SECURITY_CWE" in auth_finding.detector

    # Agreement confidence formula: 1.0 - (1 - 0.80) * (1 - 0.85) = 1.0 - (0.2 * 0.15) = 0.97
    expected_confidence = round(1.0 - (0.20 * 0.15), 4)
    assert auth_finding.raw_confidence == expected_confidence
    assert auth_finding.raw_confidence > f1.raw_confidence
    assert auth_finding.raw_confidence > f2.raw_confidence

    # Verify billing finding was preserved unmodified
    billing_finding = next(f for f in merged if f.file == "src/billing.py")
    assert billing_finding.raw_confidence == 0.75
    assert billing_finding.detector == "INPUT_VALIDATION"
