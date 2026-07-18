"""Interpret methodology confidence without implying uncalibrated probability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_contracts import ConfidenceAssessment, ConfidenceBasis


@dataclass(frozen=True, slots=True)
class ConfidenceSemantics:
    """Public interpretation of confidence labels and calibration state."""

    available: bool
    basis: str
    calibrated: bool
    probability_available: bool
    interpretation: str
    strongest_support: str | None
    strongest_contradiction: str | None
    missing_evidence: tuple[str, ...]
    model_estimated_success_rate: float | None
    sample_size: int | None


def derive_confidence_semantics(
    confidence: ConfidenceAssessment | None,
) -> ConfidenceSemantics:
    """Describe confidence honestly and reserve probability for calibration."""

    if confidence is None:
        return ConfidenceSemantics(
            available=False,
            basis="unavailable",
            calibrated=False,
            probability_available=False,
            interpretation=(
                "confidence is unavailable; no probability or certainty should be inferred"
            ),
            strongest_support=None,
            strongest_contradiction=None,
            missing_evidence=("confidence assessment", "historical calibration"),
            model_estimated_success_rate=None,
            sample_size=None,
        )

    calibrated = confidence.basis is ConfidenceBasis.HISTORICALLY_CALIBRATED
    probability_available = (
        calibrated
        and confidence.model_estimated_success_rate is not None
        and confidence.sample_size is not None
    )
    interpretation = (
        "historically calibrated estimate; still not a guaranteed outcome"
        if probability_available
        else "rule-based analytical quality label; not win probability"
    )
    return ConfidenceSemantics(
        available=True,
        basis=confidence.basis.value,
        calibrated=calibrated,
        probability_available=probability_available,
        interpretation=interpretation,
        strongest_support=confidence.strongest_support,
        strongest_contradiction=confidence.strongest_contradiction,
        missing_evidence=confidence.missing_evidence,
        model_estimated_success_rate=(
            confidence.model_estimated_success_rate if probability_available else None
        ),
        sample_size=confidence.sample_size if probability_available else None,
    )


def confidence_semantics_payload(
    semantics: ConfidenceSemantics,
) -> dict[str, Any]:
    """Serialize confidence interpretation for public and stored output."""

    return {
        "available": semantics.available,
        "basis": semantics.basis,
        "calibrated": semantics.calibrated,
        "probability_available": semantics.probability_available,
        "interpretation": semantics.interpretation,
        "strongest_support": semantics.strongest_support,
        "strongest_contradiction": semantics.strongest_contradiction,
        "missing_evidence": list(semantics.missing_evidence),
        "model_estimated_success_rate": semantics.model_estimated_success_rate,
        "sample_size": semantics.sample_size,
    }


__all__ = [
    "ConfidenceSemantics",
    "confidence_semantics_payload",
    "derive_confidence_semantics",
]
