"""Typed structural strength, regime, and range-boundary interpretation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.structure.contracts import (
    BreakQuality,
    ConfirmationStatus,
    RangeStructure,
    StructureAnalysisResult,
    TrendAnalysis,
    TrendDirection,
)


class TrendStrength(StrEnum):
    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class MarketRegime(StrEnum):
    STRONG_TREND = "strong_trend"
    WEAK_TREND = "weak_trend"
    RANGE = "range"
    BREAKOUT_EXPANSION = "breakout_expansion"
    REVERSAL_TRANSITION = "reversal_transition"
    UNCERTAIN = "uncertain"


class RangeBoundarySide(StrEnum):
    UPPER = "upper"
    LOWER = "lower"


@dataclass(frozen=True, slots=True)
class RangeBoundary:
    """One explicit boundary of a validated range."""

    side: RangeBoundarySide
    price: float
    tests: int
    tolerance: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.price) or self.price <= 0:
            raise ValueError("range boundary price must be positive and finite")
        if self.tests < 0:
            raise ValueError("range boundary tests cannot be negative")
        if not math.isfinite(self.tolerance) or self.tolerance < 0:
            raise ValueError("range boundary tolerance must be finite and non-negative")


def trend_strength_band(trend: TrendAnalysis) -> TrendStrength:
    """Map structural persistence into a stable explainable strength band."""

    if trend.direction in {TrendDirection.RANGE, TrendDirection.UNCERTAIN}:
        return TrendStrength.NONE
    if trend.strength >= 0.8:
        return TrendStrength.STRONG
    if trend.strength >= 0.5:
        return TrendStrength.MODERATE
    return TrendStrength.WEAK


def classify_market_regime(result: StructureAnalysisResult) -> MarketRegime:
    """Classify the structural environment without strategy assumptions."""

    confirmed_breaks = tuple(
        event
        for event in result.breaks
        if event.confirmation is ConfirmationStatus.CONFIRMED
        and event.quality in {BreakQuality.VALID, BreakQuality.STRONG}
    )
    if confirmed_breaks and confirmed_breaks[-1].quality is BreakQuality.STRONG:
        return MarketRegime.BREAKOUT_EXPANSION
    if result.changes_of_character or result.trend.direction is TrendDirection.TRANSITION:
        return MarketRegime.REVERSAL_TRANSITION
    if result.ranges or result.trend.direction is TrendDirection.RANGE:
        return MarketRegime.RANGE

    strength = trend_strength_band(result.trend)
    if strength is TrendStrength.STRONG:
        return MarketRegime.STRONG_TREND
    if strength in {TrendStrength.WEAK, TrendStrength.MODERATE}:
        return MarketRegime.WEAK_TREND
    return MarketRegime.UNCERTAIN


def range_boundaries(
    detected_range: RangeStructure,
    *,
    tolerance: float = 0.0,
) -> tuple[RangeBoundary, RangeBoundary]:
    """Return stable lower/upper boundaries for one validated range."""

    return (
        RangeBoundary(
            side=RangeBoundarySide.LOWER,
            price=detected_range.low,
            tests=detected_range.lower_tests,
            tolerance=tolerance,
        ),
        RangeBoundary(
            side=RangeBoundarySide.UPPER,
            price=detected_range.high,
            tests=detected_range.upper_tests,
            tolerance=tolerance,
        ),
    )
