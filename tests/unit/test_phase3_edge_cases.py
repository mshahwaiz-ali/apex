from datetime import UTC, datetime, timedelta

import pytest

from apex.domain import Candle
from apex.features import ActiveCandlePolicy
from apex.liquidity import (
    LiquiditySide,
    LiquidityZone,
    LiquidityZoneStatus,
    LiquidityZoneType,
    SweepClassification,
    derive_liquidity_zones,
    detect_liquidity_sweeps,
)
from apex.structure import (
    BreakDirection,
    ConfirmationStatus,
    PivotStatus,
    SwingPoint,
    SwingType,
    TrendDirection,
    classify_trend,
    detect_range,
    detect_structure_breaks,
    detect_swings,
)


def _time(index: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index)


def _candle(
    index: int,
    *,
    high: float,
    low: float,
    close: float,
    is_closed: bool = True,
) -> Candle:
    return Candle(
        symbol="BTC/USDT",
        timeframe="1m",
        open_time=_time(index),
        close_time=_time(index + 1),
        open=(high + low) / 2,
        high=high,
        low=low,
        close=close,
        volume=0.0,
        is_closed=is_closed,
        source="fixture",
    )


def _swing(index: int, price: float, kind: SwingType) -> SwingPoint:
    return SwingPoint(
        index=index,
        time=_time(index),
        price=price,
        kind=kind,
        status=PivotStatus.CONFIRMED,
        left_window=1,
        right_window=1,
    )


def _sell_side_zone() -> LiquidityZone:
    return LiquidityZone(
        side=LiquiditySide.SELL_SIDE,
        kind=LiquidityZoneType.PIVOT_LOW,
        low=100.0,
        high=100.0,
        representative_price=100.0,
        source_pivot_indices=(1,),
        touch_count=1,
        created_index=1,
        last_touch_index=1,
        age=1,
        status=LiquidityZoneStatus.ACTIVE,
        strength=0.5,
    )


def test_equal_lows_form_sell_side_liquidity() -> None:
    swings = (
        _swing(1, 100.0, SwingType.LOW),
        _swing(3, 100.1, SwingType.LOW),
    )

    zones = derive_liquidity_zones(swings, current_index=5, tolerance=0.002)

    equal_lows = tuple(zone for zone in zones if zone.kind is LiquidityZoneType.EQUAL_LOWS)
    assert len(equal_lows) == 1
    assert equal_lows[0].side is LiquiditySide.SELL_SIDE


def test_clean_lower_high_lower_low_sequence_is_strong_bearish() -> None:
    swings = (
        _swing(1, 110.0, SwingType.HIGH),
        _swing(2, 100.0, SwingType.LOW),
        _swing(3, 107.0, SwingType.HIGH),
        _swing(4, 97.0, SwingType.LOW),
        _swing(5, 104.0, SwingType.HIGH),
        _swing(6, 94.0, SwingType.LOW),
    )

    result = classify_trend(swings)

    assert result.direction is TrendDirection.STRONG_BEARISH
    assert result.evidence.lower_highs == 2
    assert result.evidence.lower_lows == 2


def test_configurable_thresholds_expose_weak_bullish_state() -> None:
    swings = (
        _swing(1, 100.0, SwingType.HIGH),
        _swing(2, 95.0, SwingType.LOW),
        _swing(3, 105.0, SwingType.HIGH),
        _swing(4, 94.0, SwingType.LOW),
        _swing(5, 110.0, SwingType.HIGH),
    )

    result = classify_trend(
        swings,
        minimum_pairs=2,
        weak_persistence=0.8,
        strong_persistence=0.95,
    )

    assert result.direction is TrendDirection.WEAK_BULLISH


def test_balanced_conflicting_structure_is_transition() -> None:
    swings = (
        _swing(1, 100.0, SwingType.HIGH),
        _swing(2, 95.0, SwingType.LOW),
        _swing(3, 105.0, SwingType.HIGH),
        _swing(4, 90.0, SwingType.LOW),
    )

    result = classify_trend(swings)

    assert result.direction is TrendDirection.TRANSITION


def test_active_sell_side_recovery_is_developing_sweep() -> None:
    candles = (
        _candle(0, high=102.0, low=101.0, close=101.5),
        _candle(1, high=101.0, low=100.0, close=100.5),
        _candle(2, high=101.0, low=99.0, close=100.5, is_closed=False),
    )

    events = detect_liquidity_sweeps(
        candles,
        (_sell_side_zone(),),
        relative_volume=(0.0, 0.0, 0.0),
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    )

    assert events[0].classification is SweepClassification.DEVELOPING_SWEEP
    assert "provisional" in events[0].warnings[0]


def test_zero_relative_volume_is_valid_but_not_confirmation() -> None:
    candles = (
        _candle(0, high=102.0, low=101.0, close=101.5),
        _candle(1, high=101.0, low=100.0, close=100.5),
        _candle(2, high=101.0, low=99.0, close=100.5),
    )

    events = detect_liquidity_sweeps(
        candles,
        (_sell_side_zone(),),
        relative_volume=(0.0, 0.0, 0.0),
    )

    assert events[0].classification is SweepClassification.CONFIRMED_SWEEP
    assert "lacks relative-volume confirmation" in events[0].warnings


def test_close_confirmed_bearish_break() -> None:
    candles = (
        _candle(0, high=105.0, low=101.0, close=104.0),
        _candle(1, high=104.0, low=100.0, close=103.0),
        _candle(2, high=102.0, low=97.0, close=98.0),
    )

    event = detect_structure_breaks(
        candles,
        (_swing(1, 100.0, SwingType.LOW),),
    )[0]

    assert event.direction is BreakDirection.BEARISH
    assert event.confirmation is ConfirmationStatus.CONFIRMED


def test_active_bearish_break_remains_developing() -> None:
    candles = (
        _candle(0, high=105.0, low=101.0, close=104.0),
        _candle(1, high=104.0, low=100.0, close=103.0),
        _candle(2, high=102.0, low=97.0, close=98.0, is_closed=False),
    )

    event = detect_structure_breaks(
        candles,
        (_swing(1, 100.0, SwingType.LOW),),
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    )[0]

    assert event.direction is BreakDirection.BEARISH
    assert event.confirmation is ConfirmationStatus.DEVELOPING


def test_future_pivot_is_rejected_from_liquidity_derivation() -> None:
    with pytest.raises(ValueError, match="after current_index"):
        derive_liquidity_zones(
            (_swing(5, 100.0, SwingType.HIGH),),
            current_index=4,
        )


def test_flat_market_does_not_create_zero_width_range() -> None:
    candles = tuple(
        _candle(index, high=100.0, low=100.0, close=100.0)
        for index in range(21)
    )

    assert detect_range(candles) is None


def test_confirmed_prefix_swings_do_not_change_when_future_candles_arrive() -> None:
    candles = tuple(
        _candle(index, high=high, low=low, close=(high + low) / 2)
        for index, (high, low) in enumerate(
            (
                (101.0, 99.0),
                (104.0, 100.0),
                (102.0, 98.0),
                (105.0, 100.0),
                (103.0, 97.0),
                (106.0, 101.0),
            )
        )
    )

    prefix = detect_swings(candles[:5], left_window=1, right_window=1)
    extended = detect_swings(candles, left_window=1, right_window=1)

    assert prefix == tuple(swing for swing in extended if swing.index <= 3)
