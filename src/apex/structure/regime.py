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
    STRONG_UPTREND = "strong_uptrend"
    WEAK_UPTREND = "weak_uptrend"
    STRONG_DOWNTREND = "strong_downtrend"
    WEAK_DOWNTREND = "weak_downtrend"
    STABLE_RANGE = "stable_range"
    VOLATILE_RANGE = "volatile_range"
    COMPRESSION = "compression"
    BREAKOUT_EXPANSION = "breakout_expansion"
    REVERSAL_TRANSITION = "reversal_transition"
    HIGH_VOLATILITY_CHAOS = "high_volatility_chaos"
    LOW_VOLATILITY_STAGNATION = "low_volatility_stagnation"
    LOW_LIQUIDITY = "low_liquidity"
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
        return _range_regime(result.ranges[-1] if result.ranges else None)

    strength = trend_strength_band(result.trend)
    if strength is TrendStrength.STRONG:
        return (
            MarketRegime.STRONG_DOWNTREND
            if _is_bearish(result.trend.direction)
            else MarketRegime.STRONG_UPTREND
        )
    if strength in {TrendStrength.WEAK, TrendStrength.MODERATE}:
        return (
            MarketRegime.WEAK_DOWNTREND
            if _is_bearish(result.trend.direction)
            else MarketRegime.WEAK_UPTREND
        )
    return MarketRegime.UNCERTAIN


def _is_bearish(direction: TrendDirection) -> bool:
    return direction in {
        TrendDirection.STRONG_BEARISH,
        TrendDirection.BEARISH,
        TrendDirection.WEAK_BEARISH,
    }


def _range_regime(detected_range: RangeStructure | None) -> MarketRegime:
    if detected_range is None:
        return MarketRegime.STABLE_RANGE
    if detected_range.width_percentage >= 0.12:
        return MarketRegime.VOLATILE_RANGE
    if detected_range.width_percentage <= 0.025:
        return MarketRegime.COMPRESSION
    return MarketRegime.STABLE_RANGE


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
