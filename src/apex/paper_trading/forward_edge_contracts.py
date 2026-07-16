"""Typed contracts for setup-specific forward-paper evidence."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from apex.backtesting.historical_edge import EvidenceQuality
from apex.backtesting.historical_edge_validation import HistoricalEdgeValidationResult


class ForwardPaperValidationStatus(StrEnum):
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    FAILED_VALIDATION = "FAILED_VALIDATION"
    DEGRADED_VALIDATION = "DEGRADED_VALIDATION"
    PASSED_VALIDATION = "PASSED_VALIDATION"


class ForwardPaperValidationReason(StrEnum):
    HISTORICAL_OUT_OF_SAMPLE_REQUIRED = "HISTORICAL_OUT_OF_SAMPLE_REQUIRED"
    SEGMENT_DIMENSIONS_MISMATCH = "SEGMENT_DIMENSIONS_MISMATCH"
    FORWARD_SAMPLE_INSUFFICIENT = "FORWARD_SAMPLE_INSUFFICIENT"
    FORWARD_EXPECTANCY_NOT_POSITIVE = "FORWARD_EXPECTANCY_NOT_POSITIVE"
    FORWARD_PROFIT_FACTOR_INADEQUATE = "FORWARD_PROFIT_FACTOR_INADEQUATE"
    EXPECTANCY_DEGRADATION_EXCESSIVE = "EXPECTANCY_DEGRADATION_EXCESSIVE"
    EDGE_DIRECTION_INCONSISTENT = "EDGE_DIRECTION_INCONSISTENT"
    PRODUCTION_ELIGIBILITY_NOT_INCLUDED = "PRODUCTION_ELIGIBILITY_NOT_INCLUDED"


@dataclass(frozen=True, slots=True)
class ForwardPaperValidationPolicy:
    minimum_closed_trades: int = 100
    minimum_profit_factor: float = 1.0
    maximum_expectancy_degradation_from_test: float = 0.60

    def __post_init__(self) -> None:
        if self.minimum_closed_trades < 1:
            raise ValueError("minimum closed trades must be positive")
        for name in (
            "minimum_profit_factor",
            "maximum_expectancy_degradation_from_test",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ForwardPaperEdgeProfile:
    dimensions: Mapping[str, str]
    sample_size: int
    win_rate: float
    expectancy: float
    profit_factor: float | None
    maximum_drawdown_r: float

    def __post_init__(self) -> None:
        if self.sample_size < 1:
            raise ValueError("forward-paper profile requires at least one trade")
        if not math.isfinite(self.win_rate) or not 0.0 <= self.win_rate <= 1.0:
            raise ValueError("win rate must be in the unit interval")
        for name in ("expectancy", "maximum_drawdown_r"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name.replace('_', ' ')} must be finite")
        if self.maximum_drawdown_r < 0.0:
            raise ValueError("maximum drawdown cannot be negative")
        if self.profit_factor is not None and (
            not math.isfinite(self.profit_factor) or self.profit_factor < 0.0
        ):
            raise ValueError("profit factor must be finite and non-negative")
        object.__setattr__(self, "dimensions", MappingProxyType(dict(self.dimensions)))


@dataclass(frozen=True, slots=True)
class ForwardPaperValidationResult:
    dimensions: Mapping[str, str]
    status: ForwardPaperValidationStatus
    historical_validation: HistoricalEdgeValidationResult
    forward_profile: ForwardPaperEdgeProfile | None
    expectancy_degradation_from_test: float | None
    consistent_edge_direction: bool
    evidence_stable: bool
    promoted_evidence_quality: EvidenceQuality | None
    rejection_reasons: tuple[ForwardPaperValidationReason, ...] = field(default_factory=tuple)
    warnings: tuple[ForwardPaperValidationReason, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.promoted_evidence_quality not in {
            None,
            EvidenceQuality.VALIDATED_FORWARD_PAPER,
        }:
            raise ValueError("V1.6 can only promote to validated forward paper")
        passed = self.status is ForwardPaperValidationStatus.PASSED_VALIDATION
        if passed != (self.promoted_evidence_quality is EvidenceQuality.VALIDATED_FORWARD_PAPER):
            raise ValueError("forward validation status must agree with promotion")
        if passed and self.rejection_reasons:
            raise ValueError("passed forward validation cannot contain rejection reasons")
        object.__setattr__(self, "dimensions", MappingProxyType(dict(self.dimensions)))
