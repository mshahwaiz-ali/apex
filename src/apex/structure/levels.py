"""Support and resistance extraction from structural pivots."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime

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
    for kind in (SwingType.HIGH, SwingType.LOW):
        kind_pivots = tuple(item for item in confirmed if item.kind is kind)
        for pivot in sorted(kind_pivots, key=lambda item: (item.price, item.index)):
            matching = next(
                (
                    cluster
                    for cluster in clusters
                    if cluster[0].kind is kind
                    and abs(pivot.price - _mean_price(cluster))
                    <= max(pivot.price, _mean_price(cluster)) * tolerance
                ),
                None,
            )
            if matching is None:
                clusters.append([pivot])
            else:
                matching.append(pivot)

    levels: list[StructureLevel] = []
    for cluster in clusters:
        if len(cluster) < minimum_touches:
            continue
        prices = tuple(item.price for item in cluster)
        representative = sum(prices) / len(prices)
        latest_pivot = max(cluster, key=lambda item: item.index)
        source_role = (
            LevelRole.RESISTANCE
            if latest_pivot.kind is SwingType.HIGH
            else LevelRole.SUPPORT
        )
        role, status = _classify_level_state(
            source_role,
            low=min(prices),
            high=max(prices),
            pivot_time=latest_pivot.time,
            candles=candles,
        )

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
                last_touch_index=ordered_indices[-1],
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


def _classify_level_state(
    source_role: LevelRole,
    *,
    low: float,
    high: float,
    pivot_time: datetime,
    candles: Sequence[Candle],
) -> tuple[LevelRole, LevelStatus]:
    post_pivot = tuple(candle for candle in candles if candle.open_time > pivot_time)
    if source_role is LevelRole.RESISTANCE:
        break_index = next(
            (index for index, candle in enumerate(post_pivot) if candle.close > high),
            None,
        )
        if break_index is None:
            return source_role, LevelStatus.ACTIVE
        retested = any(
            candle.low <= high and candle.close >= high
            for candle in post_pivot[break_index + 1 :]
        )
        if retested:
            return LevelRole.SUPPORT, LevelStatus.FLIPPED
        return LevelRole.RESISTANCE, LevelStatus.BROKEN

    break_index = next(
        (index for index, candle in enumerate(post_pivot) if candle.close < low),
        None,
    )
    if break_index is None:
        return source_role, LevelStatus.ACTIVE
    retested = any(
        candle.high >= low and candle.close <= low
        for candle in post_pivot[break_index + 1 :]
    )
    if retested:
        return LevelRole.RESISTANCE, LevelStatus.FLIPPED
    return LevelRole.SUPPORT, LevelStatus.BROKEN


def _mean_price(cluster: Sequence[SwingPoint]) -> float:
    return sum(item.price for item in cluster) / len(cluster)
