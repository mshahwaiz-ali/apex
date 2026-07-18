"""Canonical volatility and normal-noise evidence for structural stop assessment."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class StopNoiseMeasure(StrEnum):
    """Supported reference measures for ordinary price noise."""

    ATR = "atr"
    REALIZED_RANGE = "realized_range"
    REALIZED_VOLATILITY = "realized_volatility"


@dataclass(frozen=True, slots=True)
class StopNoiseEvidence:
    """Measured ordinary-price-noise reference for one stop assessment."""

    measure: StopNoiseMeasure
    value: float
    timeframe: str
    sample_size: int
    required_clearance_multiplier: float
    source: str

    def __post_init__(self) -> None:
        if not math.isfinite(self.value) or self.value <= 0.0:
            raise ValueError("stop noise value must be finite and positive")
        if not self.timeframe.strip():
            raise ValueError("stop noise timeframe cannot be empty")
        if self.sample_size <= 0:
            raise ValueError("stop noise sample size must be positive")
        if not math.isfinite(self.required_clearance_multiplier):
            raise ValueError("required clearance multiplier must be finite")
        if self.required_clearance_multiplier <= 0.0:
            raise ValueError("required clearance multiplier must be positive")
        if not self.source.strip():
            raise ValueError("stop noise source cannot be empty")

    @property
    def required_clearance_distance(self) -> float:
        """Minimum distance required by this explicitly configured evidence."""

        return self.value * self.required_clearance_multiplier


__all__ = ["StopNoiseEvidence", "StopNoiseMeasure"]
