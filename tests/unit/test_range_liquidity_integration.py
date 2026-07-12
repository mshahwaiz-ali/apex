from datetime import UTC, datetime, timedelta

from apex.domain import Candle
from apex.liquidity import (
    LiquiditySide,
    LiquidityZoneType,
    SweepClassification,
    derive_liquidity_zones,
    detect_liquidity_sweeps,
)
from apex.structure import RangeBreakoutState, RangeStructure


def _candle(
    index: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
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
        is_closed=True,
        source="fixture",
    )


def test_false_break_trigger_occurs_after_range_zone_history() -> None:
    detected_range = RangeStructure(
        low=95.0,
        high=105.0,
        midpoint=100.0,
        width=10.0,
        width_percentage=0.1,
        start_index=0,
        end_index=20,
        upper_tests=3,
        lower_tests=3,
        breakout_state=RangeBreakoutState.FALSE_BULLISH,
        current_position=0.8,
        quality=0.8,
        false_break_indices=(20,),
    )
    candles = tuple(
        _candle(
            index,
            open_price=100.0,
            high=106.0 if index == 20 else 104.0,
            low=96.0,
            close=104.0 if index == 20 else 100.0,
        )
        for index in range(21)
    )

    zones = derive_liquidity_zones(
        (),
        current_index=20,
        ranges=(detected_range,),
    )
    buy_side = next(
        zone
        for zone in zones
        if zone.side is LiquiditySide.BUY_SIDE and zone.kind is LiquidityZoneType.RANGE_HIGH
    )
    events = detect_liquidity_sweeps(candles, (buy_side,))

    assert buy_side.last_touch_index == 19
    assert events[0].candle_index == 20
    assert events[0].classification is SweepClassification.CONFIRMED_SWEEP
