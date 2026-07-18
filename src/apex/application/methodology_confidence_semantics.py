"""Interpret methodology confidence without implying uncalibrated probability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_calibration_contracts import CalibrationProvenance
from apex.application.methodology_contracts import ConfidenceAssessment, ConfidenceBasis


@dataclass(frozen=True, slots=True)
class ConfidenceSemantics:
    """Public interpretation of confidence labels and calibration state."""

    available: bool
    basis: str
    historically_labeled: bool
    calibration_provenance_available: bool
    out_of_sample_validated: bool
    leakage_checks_passed: bool
    costs_included: bool
    regime_stability_checked: bool
    calibrated: bool
    probability_available: bool
    interpretation: str
    strongest_support: str | None
    strongest_contradiction: str | None
    missing_evidence: tuple[str, ...]
    model_estimated_success_rate: float | None
    sample_size: int | None
    validation_sample_size: int | None
    calibration_error: float | None


def derive_confidence_semantics(
    confidence: ConfidenceAssessment | None,
    calibration: CalibrationProvenance | None = None,
) -> ConfidenceSemantics:
    """Reserve probability for fully evidenced out-of-sample calibration."""

    if confidence is None:
        return ConfidenceSemantics(
            available=False,
            basis="unavailable",
            historically_labeled=False,
            calibration_provenance_available=calibration is not None,
            out_of_sample_validated=False,
            leakage_checks_passed=False,
            costs_included=False,
            regime_stability_checked=False,
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
            validation_sample_size=None,
            calibration_error=None,
        )

    historically_labeled = confidence.basis is ConfidenceBasis.HISTORICALLY_CALIBRATED
    provenance_authoritative = bool(
        calibration is not None and calibration.authoritative_probability
    )
    probability_available = bool(
        historically_labeled
        and provenance_authoritative
        and confidence.model_estimated_success_rate is not None
        and confidence.sample_size is not None
    )

    if probability_available:
        interpretation = (
            "historically calibrated out-of-sample estimate with chronology, leakage, cost, "
            "and regime-stability provenance; still not a guaranteed outcome"
        )
    elif historically_labeled and calibration is None:
        interpretation = (
            "confidence is labeled historically calibrated, but dataset and out-of-sample "
            "provenance are unavailable; the estimate is withheld as probability"
        )
    elif historically_labeled:
        interpretation = (
            "historical calibration metadata is present but does not satisfy all authority "
            "requirements; the estimate is withheld as probability"
        )
    else:
        interpretation = "rule-based analytical quality label; not win probability"

    missing = list(confidence.missing_evidence)
    if historically_labeled and calibration is None:
        missing.append("calibration provenance")
    elif historically_labeled and calibration is not None:
        if not calibration.out_of_sample:
            missing.append("out-of-sample validation")
        if not calibration.chronological_split:
            missing.append("chronological train/validation split")
        if not calibration.leakage_checks_passed:
            missing.append("passed leakage checks")
        if not calibration.costs_included:
            missing.append("fees and slippage in validation")
        if not calibration.regime_stability_checked:
            missing.append("regime stability validation")

    return ConfidenceSemantics(
        available=True,
        basis=confidence.basis.value,
        historically_labeled=historically_labeled,
        calibration_provenance_available=calibration is not None,
        out_of_sample_validated=bool(calibration is not None and calibration.out_of_sample),
        leakage_checks_passed=bool(
            calibration is not None and calibration.leakage_checks_passed
        ),
        costs_included=bool(calibration is not None and calibration.costs_included),
        regime_stability_checked=bool(
            calibration is not None and calibration.regime_stability_checked
        ),
        calibrated=probability_available,
        probability_available=probability_available,
        interpretation=interpretation,
        strongest_support=confidence.strongest_support,
        strongest_contradiction=confidence.strongest_contradiction,
        missing_evidence=tuple(dict.fromkeys(missing)),
        model_estimated_success_rate=(
            confidence.model_estimated_success_rate if probability_available else None
        ),
        sample_size=confidence.sample_size if probability_available else None,
        validation_sample_size=(
            calibration.validation_sample_size if probability_available and calibration else None
        ),
        calibration_error=(
            calibration.calibration_error if probability_available and calibration else None
        ),
    )


def confidence_semantics_payload(
    semantics: ConfidenceSemantics,
) -> dict[str, Any]:
    """Serialize confidence interpretation for public and stored output."""

    return {
        "available": semantics.available,
        "basis": semantics.basis,
        "historically_labeled": semantics.historically_labeled,
        "calibration_provenance_available": semantics.calibration_provenance_available,
        "out_of_sample_validated": semantics.out_of_sample_validated,
        "leakage_checks_passed": semantics.leakage_checks_passed,
        "costs_included": semantics.costs_included,
        "regime_stability_checked": semantics.regime_stability_checked,
        "calibrated": semantics.calibrated,
        "probability_available": semantics.probability_available,
        "interpretation": semantics.interpretation,
        "strongest_support": semantics.strongest_support,
        "strongest_contradiction": semantics.strongest_contradiction,
        "missing_evidence": list(semantics.missing_evidence),
        "model_estimated_success_rate": semantics.model_estimated_success_rate,
        "sample_size": semantics.sample_size,
        "validation_sample_size": semantics.validation_sample_size,
        "calibration_error": semantics.calibration_error,
    }


__all__ = [
    "ConfidenceSemantics",
    "confidence_semantics_payload",
    "derive_confidence_semantics",
]