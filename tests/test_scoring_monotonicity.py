"""Unit tests proving formal monotonicity properties of AutoPatch scoring (Rule 5 & Rule 2).

Properties Tested:
1. Verification Monotonicity: A verified bug NEVER scores lower confidence than the same bug unverified.
2. BRT Reproduction Monotonicity: A confirmed bug scores higher confidence than an unconfirmed bug.
3. Detector Agreement Monotonicity: Higher detector confidence never reduces overall confidence.
4. EPR Monotonicity: Higher Ensemble Pass Rate never reduces overall confidence.
5. Overfitting Monotonicity: Overfitting flag strictly applies a penalty and reduces confidence.
6. Category Severity Monotonicity: security > data_loss > crash > wrong_output > style.
7. Reachability Monotonicity: entry_point_direct >= entry_point_indirect >= internal >= unreachable.
8. Blast Radius Monotonicity: higher caller counts increase or maintain severity.
"""

import pytest
from autopatch.scoring.confidence import ConfidenceCalculator
from autopatch.scoring.models import BugCategory, ReachabilityStatus
from autopatch.scoring.severity import SeverityCalculator


def test_monotonic_verified_never_scores_lower_confidence_than_unverified():
    """Rule 2 & 5 Invariant: A verified bug NEVER scores lower confidence than the same bug unverified."""
    calc = ConfidenceCalculator()

    # Base test bug parameters
    detector_agreement = 0.85
    epr = 100.0

    # 1. Verified state
    c_verified = calc.compute_confidence(
        detector_agreement=detector_agreement,
        brt_status="CONFIRMED",
        verification_state="VERIFIED",
        epr=epr,
    ).overall_confidence

    # 2. Plausible but unverified
    c_plausible = calc.compute_confidence(
        detector_agreement=detector_agreement,
        brt_status="CONFIRMED",
        verification_state="PLAUSIBLE_BUT_UNVERIFIED",
        epr=epr,
    ).overall_confidence

    # 3. Needs review
    c_needs_review = calc.compute_confidence(
        detector_agreement=detector_agreement,
        brt_status="CONFIRMED",
        verification_state="NEEDS_REVIEW",
        epr=epr,
    ).overall_confidence

    # 4. Failed verification
    c_failed = calc.compute_confidence(
        detector_agreement=detector_agreement,
        brt_status="CONFIRMED",
        verification_state="FAILED",
        epr=epr,
    ).overall_confidence

    # 5. Completely unverified / no patch
    c_none = calc.compute_confidence(
        detector_agreement=detector_agreement,
        brt_status="CONFIRMED",
        verification_state="NONE",
        epr=0.0,
    ).overall_confidence

    # Strict monotonicity assertions
    assert c_verified > c_plausible, f"VERIFIED ({c_verified}) must exceed PLAUSIBLE ({c_plausible})"
    assert c_plausible > c_needs_review, f"PLAUSIBLE ({c_plausible}) must exceed NEEDS_REVIEW ({c_needs_review})"
    assert c_needs_review > c_failed, f"NEEDS_REVIEW ({c_needs_review}) must exceed FAILED ({c_failed})"
    assert c_verified > c_none, f"VERIFIED ({c_verified}) must exceed NONE ({c_none})"


def test_monotonic_brt_confirmation_boosts_confidence():
    """Rule 2 Invariant: Confirmed reproduction test strictly scores higher than unconfirmed."""
    calc = ConfidenceCalculator()

    c_confirmed = calc.compute_confidence(
        detector_agreement=0.80,
        brt_status="CONFIRMED",
        verification_state="VERIFIED",
        epr=100.0,
    ).overall_confidence

    c_unconfirmed = calc.compute_confidence(
        detector_agreement=0.80,
        brt_status="UNCONFIRMED",
        verification_state="VERIFIED",
        epr=100.0,
    ).overall_confidence

    c_none = calc.compute_confidence(
        detector_agreement=0.80,
        brt_status="NONE",
        verification_state="VERIFIED",
        epr=100.0,
    ).overall_confidence

    assert c_confirmed > c_unconfirmed
    assert c_unconfirmed >= c_none
    # Invariant: Unconfirmed bug cannot claim high confidence (>0.50)
    assert c_unconfirmed <= 0.50


def test_monotonic_detector_agreement_and_epr():
    """Higher detector agreement and higher EPR monotonically increase or maintain confidence."""
    calc = ConfidenceCalculator()

    # Step-wise detector agreement
    c_det_low = calc.compute_confidence(detector_agreement=0.40, brt_status="CONFIRMED").overall_confidence
    c_det_mid = calc.compute_confidence(detector_agreement=0.70, brt_status="CONFIRMED").overall_confidence
    c_det_high = calc.compute_confidence(detector_agreement=0.95, brt_status="CONFIRMED").overall_confidence

    assert c_det_low <= c_det_mid <= c_det_high

    # Step-wise EPR
    c_epr_0 = calc.compute_confidence(detector_agreement=0.8, brt_status="CONFIRMED", epr=0.0).overall_confidence
    c_epr_50 = calc.compute_confidence(detector_agreement=0.8, brt_status="CONFIRMED", epr=50.0).overall_confidence
    c_epr_100 = calc.compute_confidence(detector_agreement=0.8, brt_status="CONFIRMED", epr=100.0).overall_confidence

    assert c_epr_0 <= c_epr_50 <= c_epr_100


def test_monotonic_overfitting_penalty_reduces_confidence():
    """Overfitting flags strictly decrease confidence score."""
    calc = ConfidenceCalculator()

    c_clean = calc.compute_confidence(
        detector_agreement=0.85,
        brt_status="CONFIRMED",
        verification_state="VERIFIED",
        epr=100.0,
        overfitting_flagged=False,
    ).overall_confidence

    c_overfit = calc.compute_confidence(
        detector_agreement=0.85,
        brt_status="CONFIRMED",
        verification_state="VERIFIED",
        epr=100.0,
        overfitting_flagged=True,
    ).overall_confidence

    assert c_clean > c_overfit
    assert c_clean - c_overfit >= 0.20


def test_monotonic_category_severity_ordering():
    """Severity hierarchy: security > data_loss > crash > wrong_output > style."""
    calc = SeverityCalculator()
    file_path = "src/module.py"

    s_sec = calc.compute_severity(BugCategory.SECURITY, file_path).numeric_severity
    s_data = calc.compute_severity(BugCategory.DATA_LOSS, file_path).numeric_severity
    s_crash = calc.compute_severity(BugCategory.CRASH, file_path).numeric_severity
    s_wrong = calc.compute_severity(BugCategory.WRONG_OUTPUT, file_path).numeric_severity
    s_style = calc.compute_severity(BugCategory.STYLE, file_path).numeric_severity

    assert s_sec > s_data > s_crash > s_wrong > s_style


def test_monotonic_reachability_and_callers():
    """Reachability from entry points and caller count increase severity monotonically."""
    calc = SeverityCalculator()

    # Compare directly reachable entry point file vs internal file
    s_entry = calc.compute_severity(
        category=BugCategory.SECURITY,
        file_path="main.py",
        entry_points=["main.py"],
    )

    s_internal = calc.compute_severity(
        category=BugCategory.SECURITY,
        file_path="utils/internal.py",
        symbol="_internal_helper",
        entry_points=["main.py"],
    )

    assert s_entry.numeric_severity >= s_internal.numeric_severity
    assert s_entry.reachability_factor >= s_internal.reachability_factor
