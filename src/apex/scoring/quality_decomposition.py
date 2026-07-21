"""Independent score decomposition with lane-aware overall quality."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from apex.application.opportunity_portfolio import OpportunityLane


class ConfidenceSemantics(StrEnum):
    EVIDENCE_STRENGTH = "evidence_strength"
    CALIBRATED_PROBABILITY = "calibrated_probability"


@dataclass(frozen=True, slots=True)
class CalibrationMetadata:
    calibrated: bool = False
    method: str | None = None
    sample_size: int | None = None
    calibration_window: str | None = None
    version: str | None = None

    def __post_init__(self) -> None:
        if self.calibrated:
            if not self.method or not self.method.strip():
                raise ValueError("calibrated metadata requires a method")
            if self.sample_size is None or self.sample_size <= 0:
                raise ValueError("calibrated metadata requires positive sample size")
        elif any(
            value is not None
            for value in (
                self.method,
                self.sample_size,
                self.calibration_window,
                self.version,
            )
        ):
            raise ValueError("uncalibrated metadata cannot include calibration details")


@dataclass(frozen=True, slots=True)
class QualityComponents:
    pattern_confidence: float
    directional_alignment: float
    setup_quality: float
    execution_quality: float
    reward_quality: float
    timing_quality: float
    data_confidence: float

    def __post_init__(self) -> None:
        for name in (
            "pattern_confidence",
            "directional_alignment",
            "setup_quality",
            "execution_quality",
            "reward_quality",
            "timing_quality",
            "data_confidence",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be finite and between zero and 100")


@dataclass(frozen=True, slots=True)
class OverallQualityResult:
    lane: OpportunityLane
    components: QualityComponents
    weights: Mapping[str, float]
    overall_trade_quality: float
    confidence_semantics: ConfidenceSemantics
    calibration: CalibrationMetadata

    def __post_init__(self) -> None:
        if not math.isfinite(self.overall_trade_quality):
            raise ValueError("overall trade quality must be finite")
        if not 0.0 <= self.overall_trade_quality <= 100.0:
            raise ValueError("overall trade quality must be between zero and 100")
        object.__setattr__(self, "weights", MappingProxyType(dict(self.weights)))


_LANE_WEIGHTS: dict[OpportunityLane, dict[str, float]] = {
    OpportunityLane.CMP_SCALP: {
        "pattern_confidence": 0.10,
        "directional_alignment": 0.10,
        "setup_quality": 0.15,
        "execution_quality": 0.25,
        "reward_quality": 0.15,
        "timing_quality": 0.15,
        "data_confidence": 0.10,
    },
    OpportunityLane.CONFIRMATION_SCALP: {
        "pattern_confidence": 0.10,
        "directional_alignment": 0.10,
        "setup_quality": 0.15,
        "execution_quality": 0.20,
        "reward_quality": 0.15,
        "timing_quality": 0.20,
        "data_confidence": 0.10,
    },
    OpportunityLane.PULLBACK_SCALP: {
        "pattern_confidence": 0.10,
        "directional_alignment": 0.15,
        "setup_quality": 0.20,
        "execution_quality": 0.20,
        "reward_quality": 0.15,
        "timing_quality": 0.10,
        "data_confidence": 0.10,
    },
    OpportunityLane.NEARBY_STRUCTURED: {
        "pattern_confidence": 0.10,
        "directional_alignment": 0.15,
        "setup_quality": 0.20,
        "execution_quality": 0.15,
        "reward_quality": 0.20,
        "timing_quality": 0.10,
        "data_confidence": 0.10,
    },
    OpportunityLane.RUNNER: {
        "pattern_confidence": 0.10,
        "directional_alignment": 0.20,
        "setup_quality": 0.20,
        "execution_quality": 0.10,
        "reward_quality": 0.20,
        "timing_quality": 0.05,
        "data_confidence": 0.15,
    },
    OpportunityLane.DEVELOPING: {
        "pattern_confidence": 0.15,
        "directional_alignment": 0.15,
        "setup_quality": 0.20,
        "execution_quality": 0.10,
        "reward_quality": 0.15,
        "timing_quality": 0.10,
        "data_confidence": 0.15,
    },
}


def quality_weights_for_lane(lane: OpportunityLane) -> Mapping[str, float]:
    return MappingProxyType(dict(_LANE_WEIGHTS[lane]))


def calculate_overall_quality(
    *,
    lane: OpportunityLane,
    components: QualityComponents,
    calibration: CalibrationMetadata | None = None,
) -> OverallQualityResult:
    metadata = calibration or CalibrationMetadata()
    weights = quality_weights_for_lane(lane)
    total = sum(getattr(components, name) * weight for name, weight in weights.items())
    semantics = (
        ConfidenceSemantics.CALIBRATED_PROBABILITY
        if metadata.calibrated
        else ConfidenceSemantics.EVIDENCE_STRENGTH
    )
    return OverallQualityResult(
        lane=lane,
        components=components,
        weights=weights,
        overall_trade_quality=round(total, 4),
        confidence_semantics=semantics,
        calibration=metadata,
    )


__all__ = [
    "CalibrationMetadata",
    "ConfidenceSemantics",
    "OverallQualityResult",
    "QualityComponents",
    "calculate_overall_quality",
    "quality_weights_for_lane",
]
