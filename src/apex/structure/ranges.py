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
    """Detect a recent bounded range and evaluate the latest candle against it."""

    if lookback < 3:
        raise ValueError("lookback must be at least 3")
    for name, value in (
        ("boundary_tolerance", boundary_tolerance),
        ("maximum_width_percentage", maximum_width_percentage),
    ):
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and non-negative")
    if maximum_width_percentage == 0:
        raise ValueError("maximum_width_percentage must be greater than zero")
    if minimum_boundary_tests < 1:
        raise ValueError("minimum_boundary_tests must be at least 1")

    usable = prepare_candles(
        candles,
        minimum_candles=lookback + 1,
        active_candle_policy=active_candle_policy,
    )
    boundary_window = usable[-(lookback + 1) : -1]
    latest = usable[-1]
    start_index = len(usable) - lookback - 1
    range_high = max(candle.high for candle in boundary_window)
    range_low = min(candle.low for candle in boundary_window)
    width = range_high - range_low
    midpoint = (range_high + range_low) / 2
    if width <= 0 or midpoint <= 0:
        return None

    width_percentage = width / midpoint
    if width_percentage > maximum_width_percentage:
        return None

    tolerance_amount = max(width * boundary_tolerance, midpoint * boundary_tolerance)
    upper_tests = sum(
        abs(candle.high - range_high) <= tolerance_amount for candle in boundary_window
    )
    lower_tests = sum(
        abs(candle.low - range_low) <= tolerance_amount for candle in boundary_window
    )
    if upper_tests < minimum_boundary_tests or lower_tests < minimum_boundary_tests:
        return None

    breakout_state = RangeBreakoutState.NONE
    false_break_indices: tuple[int, ...] = ()
    latest_index = len(usable) - 1
    if latest.close > range_high + tolerance_amount:
        breakout_state = RangeBreakoutState.BULLISH
    elif latest.close < range_low - tolerance_amount:
        breakout_state = RangeBreakoutState.BEARISH
    elif latest.high > range_high + tolerance_amount and latest.close <= range_high:
        breakout_state = RangeBreakoutState.FALSE_BULLISH
        false_break_indices = (latest_index,)
    elif latest.low < range_low - tolerance_amount and latest.close >= range_low:
        breakout_state = RangeBreakoutState.FALSE_BEARISH
        false_break_indices = (latest_index,)

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
        end_index=latest_index,
        upper_tests=upper_tests,
        lower_tests=lower_tests,
        breakout_state=breakout_state,
        current_position=current_position,
        quality=quality,
        false_break_indices=false_break_indices,
    )
