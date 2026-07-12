"""Typed contracts shared by deterministic feature calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class FeatureOutputShape(StrEnum):
    """Supported shapes returned by a feature calculation."""

    SCALAR = "scalar"
    SERIES = "series"


class MissingDataPolicy(StrEnum):
    """How unavailable warm-up values are represented."""

    NONE = "none"
    OMIT = "omit"


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    """Static, inspectable contract for one feature."""

    name: str
    minimum_candles: int
    accepts_active_candle: bool
    output_shape: FeatureOutputShape
    missing_data_policy: MissingDataPolicy = MissingDataPolicy.NONE

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("feature name cannot be empty")
        if self.minimum_candles < 1:
            raise ValueError("minimum_candles must be at least 1")


@dataclass(frozen=True, slots=True)
class FeatureResult:
    """Finite deterministic output produced by one feature."""

    spec: FeatureSpec
    values: tuple[float | None, ...]

    def __post_init__(self) -> None:
        if self.spec.output_shape is FeatureOutputShape.SCALAR and len(self.values) != 1:
            raise ValueError("scalar features must return exactly one value")
        if not self.values:
            raise ValueError("feature result cannot be empty")
        for value in self.values:
            if value is not None and not math.isfinite(value):
                raise ValueError("feature results cannot contain NaN or infinite values")

    @property
    def latest(self) -> float | None:
        """Return the most recent value."""

        return self.values[-1]
