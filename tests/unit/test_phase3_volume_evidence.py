from datetime import UTC, datetime, timedelta

from apex.domain import Candle
from apex.liquidity import (
    LiquiditySide,
    LiquidityZone,
    LiquidityZoneStatus,
    LiquidityZoneType,
    detect_liquidity_sweeps,
)
from apex.structure import (
    PivotStatus,
    SwingPoint,
    SwingType,
    detect_structure_breaks,
)


def _candle(index: int, *, high: float, low: float, close: float) -> Candle:
    opened = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
    return Candle(
        symbol="BTC/USDT",
        timeframe="1m",
        open_time=opened,
        close_time=opened + timedelta(minutes=1),
        open=(high + low) / 2,
        high=high,
        low=low,
        close=close,
        volume=10.0,
        is_closed=True,
        source="fixture",
    )


def _swing() -> SwingPoint:
    return SwingPoint(
        index=1,
        time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=1),
        price=100.0,
        kind=SwingType.HIGH,
        status=PivotStatus.CONFIRMED,
        left_window=1,
        right_window=1,
    )


def _zone() -> LiquidityZone:
    return LiquidityZone(
        side=LiquiditySide.BUY_SIDE,
        kind=LiquidityZoneType.PIVOT_HIGH,
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


def test_high_relative_volume_is_added_to_break_evidence() -> None:
    candles = (
        _candle(0, high=99.0, low=95.0, close=98.0),
        _candle(1, high=100.0, low=96.0, close=99.0),
        _candle(2, high=103.0, low=98.0, close=102.0),
    )

    event = detect_structure_breaks(
        candles,
        (_swing(),),
        relative_volume=(1.0, 1.0, 1.5),
    )[0]

    assert "relative volume confirmed participation in the break" in event.evidence
    assert "break lacks relative-volume confirmation" not in event.warnings


def test_low_relative_volume_warns_on_close_confirmed_break() -> None:
    candles = (
        _candle(0, high=99.0, low=95.0, close=98.0),
        _candle(1, high=100.0, low=96.0, close=99.0),
        _candle(2, high=103.0, low=98.0, close=102.0),
    )

    event = detect_structure_breaks(
        candles,
        (_swing(),),
        relative_volume=(1.0, 1.0, 0.8),
    )[0]

    assert "break lacks relative-volume confirmation" in event.warnings


def test_high_relative_volume_is_added_to_sweep_evidence() -> None:
    candles = (
        _candle(0, high=99.0, low=98.0, close=98.5),
        _candle(1, high=100.0, low=98.5, close=99.5),
        _candle(2, high=101.0, low=99.0, close=99.5),
    )

    event = detect_liquidity_sweeps(
        candles,
        (_zone(),),
        relative_volume=(1.0, 1.0, 1.5),
    )[0]

    assert (
        "relative volume confirmed participation at the liquidity event"
        in event.evidence
    )
