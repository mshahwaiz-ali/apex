from datetime import UTC, datetime, timedelta

import pytest

from apex.domain import Candle
from apex.liquidity import (
    LiquiditySide,
    LiquidityZone,
    LiquidityZoneStatus,
    LiquidityZoneType,
    SweepClassification,
    TrapType,
    create_default_liquidity_registry,
    derive_liquidity_zones,
    detect_liquidity_sweeps,
    detect_traps,
)
from apex.structure import PivotStatus, SwingPoint, SwingType


def _candle(
    index: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
    is_closed: bool = True,
) -> Candle:
    opened = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
    return Candle(
        symbol="BTC/USDT",
        timeframe="1m",
        open_time=opened,
        close_time=opened + timedelta(minutes=1),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=10.0,
        is_closed=is_closed,
        source="fixture",
    )


def _swing(index: int, price: float, kind: SwingType) -> SwingPoint:
    return SwingPoint(
        index=index,
        time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index),
        price=price,
        kind=kind,
        status=PivotStatus.CONFIRMED,
        left_window=1,
        right_window=1,
    )


def _zone(side: LiquiditySide) -> LiquidityZone:
    return LiquidityZone(
        side=side,
        kind=(
            LiquidityZoneType.PIVOT_HIGH
            if side is LiquiditySide.BUY_SIDE
            else LiquidityZoneType.PIVOT_LOW
        ),
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


def test_equal_highs_form_one_buy_side_zone() -> None:
    swings = (
        _swing(1, 100.0, SwingType.HIGH),
        _swing(3, 100.1, SwingType.HIGH),
        _swing(2, 95.0, SwingType.LOW),
    )

    zones = derive_liquidity_zones(swings, current_index=5, tolerance=0.002)
    equal_highs = tuple(item for item in zones if item.kind is LiquidityZoneType.EQUAL_HIGHS)

    assert len(equal_highs) == 1
    assert equal_highs[0].side is LiquiditySide.BUY_SIDE
    assert equal_highs[0].touch_count == 2


def test_buy_side_breach_closing_back_inside_is_confirmed_sweep() -> None:
    candles = (
        _candle(0, open_price=99.0, high=99.5, low=98.5, close=99.0),
        _candle(1, open_price=99.0, high=100.0, low=98.8, close=99.6),
        _candle(2, open_price=99.8, high=101.0, low=99.0, close=99.5),
    )

    events = detect_liquidity_sweeps(candles, (_zone(LiquiditySide.BUY_SIDE),))

    assert len(events) == 1
    assert events[0].classification is SweepClassification.CONFIRMED_SWEEP
    assert events[0].penetration == pytest.approx(0.01)


def test_sustained_buy_side_close_is_breakout_not_sweep() -> None:
    candles = (
        _candle(0, open_price=99.0, high=99.5, low=98.5, close=99.0),
        _candle(1, open_price=99.0, high=100.0, low=98.8, close=99.6),
        _candle(2, open_price=99.8, high=102.0, low=99.5, close=101.5),
    )

    events = detect_liquidity_sweeps(candles, (_zone(LiquiditySide.BUY_SIDE),))

    assert events[0].classification is SweepClassification.SIMPLE_BREAKOUT


def test_confirmed_buy_side_sweep_with_bearish_follow_through_is_bull_trap() -> None:
    candles = (
        _candle(0, open_price=99.0, high=99.5, low=98.5, close=99.0),
        _candle(1, open_price=99.0, high=100.0, low=98.8, close=99.6),
        _candle(2, open_price=99.8, high=101.0, low=99.0, close=99.5),
        _candle(3, open_price=99.4, high=99.6, low=98.0, close=98.5),
    )
    sweeps = detect_liquidity_sweeps(candles, (_zone(LiquiditySide.BUY_SIDE),))

    traps = detect_traps(candles, sweeps)

    assert len(traps) == 1
    assert traps[0].kind is TrapType.BULL_TRAP


def test_liquidity_registry_names_are_stable() -> None:
    registry = create_default_liquidity_registry()

    assert registry.names == ("market_liquidity",)
    with pytest.raises(KeyError):
        registry.get("private_helper")
