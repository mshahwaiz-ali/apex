"""Support and resistance extraction from structural pivots."""

from __future__ import annotations

import math
from collections.abc import Sequence

from apex.domain.models import Candle
from apex.structure.contracts import (
    LevelRole,
    LevelStatus,
    PivotStatus,
    StructureLevel,
    SwingPoint,
    SwingType,
)


def derive_structure_levels(
    swings: Sequence[SwingPoint],
    candles: Sequence[Candle],
    *,
    tolerance: float = 0.002,
    minimum_touches: int = 1,
) -> tuple[StructureLevel, ...]:
    """Cluster nearby confirmed pivot prices into stable structural levels."""

    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and non-negative")
    if minimum_touches < 1:
        raise ValueError("minimum_touches must be at least 1")

    confirmed = tuple(item for item in swings if item.status is PivotStatus.CONFIRMED)
    clusters: list[list[SwingPoint]] = []
    for pivot in sorted(confirmed, key=lambda item: (item.price, item.index, item.kind.value)):
        matching = next(
            (
                cluster
                for cluster in clusters
                if abs(pivot.price - _mean_price(cluster))
                <= max(pivot.price, _mean_price(cluster)) * tolerance
            ),
            None,
        )
        if matching is None:
            clusters.append([pivot])
        else:
            matching.append(pivot)

    latest_close = candles[-1].close if candles else None
    levels: list[StructureLevel] = []
    for cluster in clusters:
        if len(cluster) < minimum_touches:
            continue
        prices = tuple(item.price for item in cluster)
        representative = sum(prices) / len(prices)
        latest_pivot = max(cluster, key=lambda item: item.index)
        role = (
            LevelRole.RESISTANCE
            if latest_pivot.kind is SwingType.HIGH
            else LevelRole.SUPPORT
        )
        status = LevelStatus.ACTIVE
        if latest_close is not None:
            if role is LevelRole.RESISTANCE and latest_close > max(prices):
                status = LevelStatus.FLIPPED
                role = LevelRole.SUPPORT
            elif role is LevelRole.SUPPORT and latest_close < min(prices):
                status = LevelStatus.FLIPPED
                role = LevelRole.RESISTANCE

        ordered_indices = tuple(sorted(item.index for item in cluster))
        levels.append(
            StructureLevel(
                representative_price=representative,
                low=min(prices),
                high=max(prices),
                role=role,
                status=status,
                touches=len(cluster),
                pivot_indices=ordered_indices,
                last_touch_index=max(ordered_indices),
            )
        )

    return tuple(
        sorted(
            levels,
            key=lambda item: (
                item.representative_price,
                item.role.value,
                item.last_touch_index,
            ),
        )
    )


def _mean_price(cluster: Sequence[SwingPoint]) -> float:
    return sum(item.price for item in cluster) / len(cluster)
