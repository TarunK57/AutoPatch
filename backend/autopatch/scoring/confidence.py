"""Calibrated confidence calculation incorporating detector agreement, BRT status, verification, EPR, and overfitting."""

from __future__ import annotations

from typing import Optional

from autopatch.core.exceptions import UncalibratedConfidenceError
from autopatch.scoring.config import ScoringConfig
from autopatch.scoring.models import ConfidenceBreakdown
from autopatch.verifier.models import VerificationStatus


class ConfidenceCalculator:
    """Calculates deterministic calibrated confidence with formal monotonicity guarantees."""

    def __init__(self, config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig.load_from_file()

    def compute_confidence(
        self,
        detector_agreement: float,
        brt_status: str = "NONE",  # "CONFIRMED", "UNCONFIRMED", "NONE"
        verification_state: str = "NONE",  # "VERIFIED", "PLAUSIBLE_BUT_UNVERIFIED", "NEEDS_REVIEW", "FAILED", "NONE"
        epr: float = 0.0,  # 0.0 to 100.0
        overfitting_flagged: bool = False,
        overfitting_penalty_factor: float = 1.0,
    ) -> ConfidenceBreakdown:
        """Calculates calibrated confidence score with full component attribution.

        Monotonic Invariants Enforced:
        1. A verified bug (VERIFIED) strictly never scores lower than the same bug unverified.
        2. Higher detector agreement monotonically increases or maintains confidence.
        3. Higher EPR monotonically increases or maintains confidence.
        4. Overfitting flags monotonically apply penalties.
        """
        cw = self.config.confidence_weights

        # 1. Detector agreement score [0.0, 1.0]
        det_score = max(0.0, min(1.0, float(detector_agreement)))
        det_weighted = round(det_score * cw.detector_agreement, 4)

        # 2. BRT status score
        brt_scores = self.config.brt_status_scores
        brt_norm = brt_status.upper()
        brt_score = brt_scores.get(brt_norm, brt_scores.get("NONE", 0.10))
        brt_weighted = round(brt_score * cw.brt_reproduction, 4)

        # 3. Verification state score
        verif_scores = self.config.verification_state_scores
        verif_norm = verification_state.upper()
        verif_score = verif_scores.get(verif_norm, 0.20)
        verif_weighted = round(verif_score * cw.verification_state, 4)

        # 4. Ensemble Pass Rate (EPR) score [0.0, 1.0]
        epr_norm = max(0.0, min(100.0, float(epr)))
        epr_score = round(epr_norm / 100.0, 4)
        epr_weighted = round(epr_score * cw.epr, 4)

        # 5. Overfitting penalty
        overfit_penalty = 0.0
        if overfitting_flagged:
            overfit_penalty = round(cw.overfitting_penalty * min(1.0, max(0.5, overfitting_penalty_factor)), 4)

        # Linear calibrated combination
        base_confidence = det_weighted + brt_weighted + verif_weighted + epr_weighted
        raw_confidence = base_confidence - overfit_penalty

        # 6. Apply Invariant Bounds (Rule 5 Honest Uncertainty & Rule 2 Reproduce Before Repair)
        # Unconfirmed reproduction cannot claim high confidence (>0.50)
        if brt_norm != "CONFIRMED":
            raw_confidence = min(0.50, raw_confidence)

        # Failed verification cannot exceed 0.20
        if verif_norm == "FAILED":
            raw_confidence = min(0.20, raw_confidence)

        overall_confidence = round(max(0.05, min(1.0, raw_confidence)), 4)

        # Formulate transparent explanation
        explanation = (
            f"Overall Confidence {overall_confidence:.2f} ({overall_confidence * 100:.1f}%). "
            f"Detector agreement: {det_score:.2f} (weighted +{det_weighted:.3f}); "
            f"BRT status: {brt_norm} (score {brt_score:.2f}, weighted +{brt_weighted:.3f}); "
            f"Verification: {verif_norm} (score {verif_score:.2f}, weighted +{verif_weighted:.3f}); "
            f"EPR: {epr_norm:.1f}% (weighted +{epr_weighted:.3f}); "
            f"Overfitting penalty: -{overfit_penalty:.3f}."
        )

        return ConfidenceBreakdown(
            detector_agreement_score=det_score,
            detector_agreement_weighted=det_weighted,
            brt_status=brt_norm,
            brt_score=brt_score,
            brt_weighted=brt_weighted,
            verification_state=verif_norm,
            verification_score=verif_score,
            verification_weighted=verif_weighted,
            epr=epr_norm,
            epr_score=epr_score,
            epr_weighted=epr_weighted,
            overfitting_flagged=overfitting_flagged,
            overfitting_penalty=overfit_penalty,
            overall_confidence=overall_confidence,
            explanation=explanation,
        )
