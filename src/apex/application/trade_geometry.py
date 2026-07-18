"Shared structural stop and target geometry."

from __future__ import annotations

import math
from dataclasses import dataclass

from apex.strategies.contracts import (
    InvalidationType,
    TargetLevel,
    TradeDirection,
)


@dataclass(frozen=True, slots=True)
class StopGeometry:
    "Final stop after applying one and only one noise buffer."

    price: float
    distance: float
    distance_pct: float
    buffer: float
    buffer_reason: str

    def __post_init__(self) -> None:
        for name, value in (
            ("stop price", self.price),
            ("stop distance", self.distance),
            ("stop distance percentage", self.distance_pct),
            ("stop buffer", self.buffer),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.price <= 0.0:
            raise ValueError("stop price must be positive")
        if not self.buffer_reason.strip():
            raise ValueError("stop buffer reason cannot be empty")


def build_stop_geometry(
    *,
    direction: TradeDirection,
    preferred_entry: float,
    invalidation_price: float,
    invalidation_type: InvalidationType,
    atr: float | None,
    minimum_buffer_pct: float = 0.10,
    structural_buffer_atr: float = 0.25,
) -> StopGeometry:
    "Apply a single buffer outside raw thesis invalidation."

    for name, value in (
        ("preferred entry", preferred_entry),
        ("invalidation price", invalidation_price),
    ):
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"{name} must be positive and finite")
    if atr is not None and (not math.isfinite(atr) or atr <= 0.0):
        raise ValueError("ATR must be positive and finite when provided")

    percentage_buffer = preferred_entry * minimum_buffer_pct / 100.0
    if invalidation_type is InvalidationType.VOLATILITY:
        buffer = percentage_buffer
        reason = f"single minimum {minimum_buffer_pct:g}% execution buffer"
    else:
        atr_buffer = 0.0 if atr is None else atr * structural_buffer_atr
        buffer = max(percentage_buffer, atr_buffer)
        reason = (
            f"single {structural_buffer_atr:g} ATR structural-noise buffer"
            if atr is not None and atr_buffer >= percentage_buffer
            else f"single minimum {minimum_buffer_pct:g}% structural-noise buffer"
        )

    price = (
        invalidation_price - buffer
        if direction is TradeDirection.LONG
        else invalidation_price + buffer
    )
    if price <= 0.0:
        raise ValueError("buffered stop price must remain positive")
    distance = abs(preferred_entry - price)
    return StopGeometry(
        price=price,
        distance=distance,
        distance_pct=distance / preferred_entry * 100.0,
        buffer=buffer,
        buffer_reason=reason,
    )


def build_layered_targets(
    *,
    direction: TradeDirection,
    preferred_entry: float,
    stop_price: float,
    strategy_targets: tuple[TargetLevel, ...],
) -> tuple[TargetLevel, ...]:
    "Normalize strategy-supplied targets without inventing risk-multiple levels."

    if not strategy_targets:
        raise ValueError("at least one strategy target is required")
    if abs(preferred_entry - stop_price) <= 0.0:
        raise ValueError("stop must differ from preferred entry")

    ordered = tuple(
        sorted(
            strategy_targets,
            key=lambda level: abs(level.price - preferred_entry),
        )
    )
    results: list[TargetLevel] = []
    for index, level in enumerate(ordered, start=1):
        results.append(
            TargetLevel(
                kind=level.kind,
                price=level.price,
                label=f"TP{index}",
                rationale=level.rationale,
            )
        )

    return tuple(results[:3])


__all__ = ["StopGeometry", "build_layered_targets", "build_stop_geometry"]
