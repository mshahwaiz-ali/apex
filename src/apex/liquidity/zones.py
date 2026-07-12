"""Liquidity-zone derivation from structural pivots and ranges."""

from __future__ import annotations

import math
from collections.abc import Sequence

from apex.liquidity.contracts import (
    LiquiditySide,
    LiquidityZone,
    LiquidityZoneStatus,
    LiquidityZoneType,
)
from apex.structure.contracts import PivotStatus, RangeStructure, SwingPoint, SwingType


def derive_liquidity_zones(
    swings: Sequence[SwingPoint],
    *,
    current_index: int,
    tolerance: float = 0.002,
    ranges: Sequence[RangeStructure] = (),
) -> tuple[LiquidityZone, ...]:
    """Cluster confirmed pivots into deterministic buy-side and sell-side zones."""

    if current_index < 0:
        raise ValueError("current_index cannot be negative")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and non-negative")

    zones: list[LiquidityZone] = []
    confirmed = tuple(item for item in swings if item.status is PivotStatus.CONFIRMED)
    for kind in (SwingType.HIGH, SwingType.LOW):
        pivots = tuple(item for item in confirmed if item.kind is kind)
        for cluster in _cluster_pivots(pivots, tolerance):
            prices = tuple(item.price for item in cluster)
            representative = sum(prices) / len(prices)
            side = LiquiditySide.BUY_SIDE if kind is SwingType.HIGH else LiquiditySide.SELL_SIDE
            if len(cluster) >= 2:
                zone_type = (
                    LiquidityZoneType.EQUAL_HIGHS
                    if kind is SwingType.HIGH
                    else LiquidityZoneType.EQUAL_LOWS
                )
            else:
                zone_type = (
                    LiquidityZoneType.PIVOT_HIGH
                    if kind is SwingType.HIGH
                    else LiquidityZoneType.PIVOT_LOW
                )
            indices = tuple(sorted(item.index for item in cluster))
            age = max(0, current_index - max(indices))
            strength = min(1.0, 0.35 + 0.2 * len(cluster) + 0.45 / (1 + age))
            zones.append(
                LiquidityZone(
                    side=side,
                    kind=zone_type,
                    low=min(prices),
                    high=max(prices),
                    representative_price=representative,
                    source_pivot_indices=indices,
                    touch_count=len(indices),
                    created_index=min(indices),
                    last_touch_index=max(indices),
                    age=age,
                    status=LiquidityZoneStatus.ACTIVE,
                    strength=strength,
                )
            )

    for detected_range in ranges:
        zones.extend(_range_zones(detected_range, current_index))

    return tuple(
        sorted(
            zones,
            key=lambda item: (
                item.representative_price,
                item.side.value,
                item.kind.value,
                item.created_index,
            ),
        )
    )


def _cluster_pivots(
    pivots: Sequence[SwingPoint], tolerance: float
) -> tuple[tuple[SwingPoint, ...], ...]:
    clusters: list[list[SwingPoint]] = []
    for pivot in sorted(pivots, key=lambda item: (item.price, item.index)):
        matching = next(
            (
                cluster
                for cluster in clusters
                if abs(pivot.price - _mean(cluster)) <= max(pivot.price, _mean(cluster)) * tolerance
            ),
            None,
        )
        if matching is None:
            clusters.append([pivot])
        else:
            matching.append(pivot)
    return tuple(tuple(cluster) for cluster in clusters)


def _mean(cluster: Sequence[SwingPoint]) -> float:
    return sum(item.price for item in cluster) / len(cluster)


def _range_zones(detected_range: RangeStructure, current_index: int) -> tuple[LiquidityZone, ...]:
    age = max(0, current_index - detected_range.end_index)
    common = {
        "source_pivot_indices": (detected_range.start_index, detected_range.end_index),
        "touch_count": 2,
        "created_index": detected_range.start_index,
        "last_touch_index": detected_range.end_index,
        "age": age,
        "status": LiquidityZoneStatus.ACTIVE,
        "strength": detected_range.quality,
    }
    return (
        LiquidityZone(
            side=LiquiditySide.BUY_SIDE,
            kind=LiquidityZoneType.RANGE_HIGH,
            low=detected_range.high,
            high=detected_range.high,
            representative_price=detected_range.high,
            **common,
        ),
        LiquidityZone(
            side=LiquiditySide.SELL_SIDE,
            kind=LiquidityZoneType.RANGE_LOW,
            low=detected_range.low,
            high=detected_range.low,
            representative_price=detected_range.low,
            **common,
        ),
    )
