from datetime import UTC, datetime, timedelta

from apex.domain import Candle
from apex.structure import (
    LevelRole,
    LevelStatus,
    PivotStatus,
    SwingPoint,
    SwingType,
    derive_structure_levels,
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


def _candle(
    index: int, close: float, *, high: float | None = None, low: float | None = None
) -> Candle:
    opened = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
    return Candle(
        symbol="BTC/USDT",
        timeframe="1m",
        open_time=opened,
        close_time=opened + timedelta(minutes=1),
        open=close,
        high=high if high is not None else close + 1,
        low=low if low is not None else close - 1,
        close=close,
        volume=10.0,
        is_closed=True,
        source="fixture",
    )


def test_levels_cluster_same_role_pivots_only() -> None:
    swings = (
        _swing(1, 100.0, SwingType.HIGH),
        _swing(2, 100.1, SwingType.HIGH),
        _swing(3, 100.05, SwingType.LOW),
    )

    levels = derive_structure_levels(swings, (_candle(4, 99.0),), tolerance=0.002)

    assert len(levels) == 2
    resistance = next(level for level in levels if level.touches == 2)
    support = next(level for level in levels if level.touches == 1)
    assert resistance.pivot_indices == (1, 2)
    assert support.pivot_indices == (3,)


def test_close_beyond_resistance_marks_level_broken_before_retest() -> None:
    swings = (
        _swing(1, 100.0, SwingType.HIGH),
        _swing(3, 100.1, SwingType.HIGH),
    )

    levels = derive_structure_levels(swings, (_candle(4, 102.0),), tolerance=0.002)

    assert levels[0].role is LevelRole.RESISTANCE
    assert levels[0].status is LevelStatus.BROKEN


def test_resistance_flips_to_support_after_successful_retest() -> None:
    swings = (
        _swing(1, 100.0, SwingType.HIGH),
        _swing(3, 100.1, SwingType.HIGH),
    )
    candles = (
        _candle(4, 102.0),
        _candle(5, 100.5, high=101.0, low=99.8),
    )

    levels = derive_structure_levels(swings, candles, tolerance=0.002)

    assert levels[0].role is LevelRole.SUPPORT
    assert levels[0].status is LevelStatus.FLIPPED


def test_level_sorting_is_deterministic() -> None:
    swings = (
        _swing(1, 90.0, SwingType.LOW),
        _swing(3, 100.0, SwingType.HIGH),
        _swing(5, 110.0, SwingType.HIGH),
    )

    first = derive_structure_levels(swings, (_candle(6, 100.0),))
    second = derive_structure_levels(swings, (_candle(6, 100.0),))

    assert first == second
    assert tuple(level.representative_price for level in first) == tuple(
        sorted(level.representative_price for level in first)
    )
