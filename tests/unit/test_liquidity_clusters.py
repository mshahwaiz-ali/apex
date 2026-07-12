from datetime import UTC, datetime, timedelta

from apex.liquidity import LiquidityZoneType, derive_liquidity_zones
from apex.structure import PivotStatus, SwingPoint, SwingType


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


def test_broader_high_cluster_is_not_mislabeled_equal_highs() -> None:
    swings = (
        _swing(1, 100.0, SwingType.HIGH),
        _swing(3, 100.15, SwingType.HIGH),
    )

    zones = derive_liquidity_zones(swings, current_index=5)

    assert zones[0].kind is LiquidityZoneType.CLUSTERED_HIGHS


def test_broader_low_cluster_is_not_mislabeled_equal_lows() -> None:
    swings = (
        _swing(1, 100.0, SwingType.LOW),
        _swing(3, 100.15, SwingType.LOW),
    )

    zones = derive_liquidity_zones(swings, current_index=5)

    assert zones[0].kind is LiquidityZoneType.CLUSTERED_LOWS
