"""Canonical provenance for historical calibration and validation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CalibrationProvenance:
    """Evidence required before a historical probability can be authoritative."""

    segment_key: str
    strategy_version: str
    dataset_id: str
    training_start: datetime
    training_end: datetime
    validation_start: datetime
    validation_end: datetime
    training_sample_size: int
    validation_sample_size: int
    out_of_sample: bool
    chronological_split: bool
    leakage_checks_passed: bool
    costs_included: bool
    regime_stability_checked: bool
    calibration_error: float | None = None

    def __post_init__(self) -> None:
        for field_name, text in (
            ("segment key", self.segment_key),
            ("strategy version", self.strategy_version),
            ("dataset id", self.dataset_id),
        ):
            if not text.strip():
                raise ValueError(f"{field_name} cannot be empty")
        for field_name, timestamp in (
            ("training start", self.training_start),
            ("training end", self.training_end),
            ("validation start", self.validation_start),
            ("validation end", self.validation_end),
        ):
            _aware(field_name, timestamp)
        if self.training_end <= self.training_start:
            raise ValueError("training end must be after training start")
        if self.validation_end <= self.validation_start:
            raise ValueError("validation end must be after validation start")
        if self.chronological_split and self.validation_start < self.training_end:
            raise ValueError("chronological validation cannot overlap training")
        if self.training_sample_size <= 0 or self.validation_sample_size <= 0:
            raise ValueError("calibration sample sizes must be positive")
        if self.calibration_error is not None:
            if not math.isfinite(self.calibration_error):
                raise ValueError("calibration error must be finite")
            if not 0.0 <= self.calibration_error <= 1.0:
                raise ValueError("calibration error must be between zero and one")

    @property
    def authoritative_probability(self) -> bool:
        return (
            self.out_of_sample
            and self.chronological_split
            and self.leakage_checks_passed
            and self.costs_included
            and self.regime_stability_checked
        )


__all__ = ["CalibrationProvenance"]
