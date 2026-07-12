"""Deterministic range and consolidation detection."""

from __future__ import annotations

import math
from collections.abc import Sequence

from apex.domain.models import Candle
from apex.features.validation import ActiveCandlePolicy, prepare_candles
from apex.structure.contracts import RangeBreakoutState, RangeStructure


def detect_range(
    candles: Sequence[Candle],
    *,
    lookback: int = 20,
    boundary_tolerance: float = 0.002,
    maximum_width_percentage: float = 0.08,
    minimum_boundary_tests: int = 2,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> RangeStructure | None:
    """Detect one recent bounded range using explainable geometric rules."""

    if lookback < 3:
        raise ValueError("lookback must be at least 3")
    for name, value in (
        ("boundary_tolerance", boundary_tolerance),
        ("maximum_width_percentage", maximum_width_percentage),
    ):
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and non-negative")
    if minimum_boundary_tests < 1:
        raise ValueError("minimum_boundary_tests must be at least 1")

    usable = prepare_candles(
        candles,
        minimum_candles=lookback,
        active_candle_policy=active_candle_policy,
    )
    window = usable[-lookback:]
    start_index = len(usable) - lookback
    range_high = max(candle.high for candle in window)
    range_low = min(candle.low for candle in window)
    width = range_high - range_low
    midpoint = (range_high + range_low) / 2
    if width <= 0 or midpoint <= 0:
        return None

    width_percentage = width / midpoint
    if width_percentage > maximum_width_percentage:
        return None

    tolerance_amount = max(width * boundary_tolerance, midpoint * boundary_tolerance)
    upper_tests = sum(abs(candle.high - range_high) <= tolerance_amount for candle in window)
    lower_tests = sum(abs(candle.low - range_low) <= tolerance_amount for candle in window)
    if upper_tests < minimum_boundary_tests or lower_tests < minimum_boundary_tests:
        return None

    latest = window[-1]
    breakout_state = RangeBreakoutState.NONE
    false_break_indices: list[int] = []
    for offset, candle in enumerate(window):
        absolute_index = start_index + offset
        if candle.high > range_high + tolerance_amount and candle.close <= range_high:
            false_break_indices.append(absolute_index)
        elif candle.low < range_low - tolerance_amount and candle.close >= range_low:
            false_break_indices.append(absolute_index)

    if latest.close > range_high + tolerance_amount:
        breakout_state = RangeBreakoutState.BULLISH
    elif latest.close < range_low - tolerance_amount:
        breakout_state = RangeBreakoutState.BEARISH
    elif latest.high > range_high + tolerance_amount and latest.close <= range_high:
        breakout_state = RangeBreakoutState.FALSE_BULLISH
    elif latest.low < range_low - tolerance_amount and latest.close >= range_low:
        breakout_state = RangeBreakoutState.FALSE_BEARISH

    current_position = min(1.0, max(0.0, (latest.close - range_low) / width))
    test_score = min(1.0, (upper_tests + lower_tests) / (2 * minimum_boundary_tests))
    width_score = 1.0 - min(1.0, width_percentage / maximum_width_percentage)
    quality = (test_score + width_score) / 2

    return RangeStructure(
        low=range_low,
        high=range_high,
        midpoint=midpoint,
        width=width,
        width_percentage=width_percentage,
        start_index=start_index,
        end_index=len(usable) - 1,
        upper_tests=upper_tests,
        lower_tests=lower_tests,
        breakout_state=breakout_state,
        current_position=current_position,
        quality=quality,
        false_break_indices=tuple(false_break_indices),
    )
