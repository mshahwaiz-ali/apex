"""Shared structural stop and target geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum

from apex.strategies.contracts import (
    InvalidationType,
    TargetLevel,
    TargetType,
    TradeDirection,
)


class TargetSourcePriority(IntEnum):
    STRUCTURAL = 0
    LIQUIDITY = 1
    RANGE = 2
    EXPANSION = 3
    PARTIAL = 4


_TARGET_SOURCE_PRIORITY = {
    TargetType.STRUCTURAL: TargetSourcePriority.STRUCTURAL,
    TargetType.LIQUIDITY: TargetSourcePriority.LIQUIDITY,
    TargetType.RANGE: TargetSourcePriority.RANGE,
    TargetType.EXPANSION: TargetSourcePriority.EXPANSION,
    TargetType.PARTIAL: TargetSourcePriority.PARTIAL,
}


@dataclass(frozen=True, slots=True)
class StopGeometry:
    """Final stop after applying one and only one noise buffer."""

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


def _adaptive_structural_buffer_atr(
    *,
    preferred_entry: float,
    atr: float,
    configured_floor: float,
) -> tuple[float, str]:
    """Return a symbol-relative ATR noise floor for structural invalidation.

    The ATR percentage makes the policy naturally adapt to each symbol instead
    of assigning the same absolute behaviour to BTC, ETH and small-cap futures.
    The floor grows gradually with volatility, while an entry-relative cap keeps
    extreme candles from creating an untradeably wide stop.
    """

    atr_pct = atr / preferred_entry * 100.0
    if atr_pct < 0.25:
        adaptive_floor = 0.45
        volatility_band = "low"
    elif atr_pct < 0.75:
        adaptive_floor = 0.60
        volatility_band = "normal"
    elif atr_pct < 1.50:
        adaptive_floor = 0.75
        volatility_band = "high"
    else:
        adaptive_floor = 0.90
        volatility_band = "extreme"

    requested_ratio = max(configured_floor, adaptive_floor)
    maximum_buffer = preferred_entry * 1.25 / 100.0
    effective_ratio = min(requested_ratio, maximum_buffer / atr)
    return max(0.0, effective_ratio), volatility_band


def build_stop_geometry(
    *,
    direction: TradeDirection,
    preferred_entry: float,
    invalidation_price: float,
    invalidation_type: InvalidationType,
    atr: float | None,
    minimum_buffer_pct: float = 0.10,
    structural_buffer_atr: float = 0.25,
    invalidation_already_buffered: bool = False,
    execution_buffer_override: float | None = None,
) -> StopGeometry:
    """Apply a single symbol-relative buffer outside raw thesis invalidation."""

    for name, value in (
        ("preferred entry", preferred_entry),
        ("invalidation price", invalidation_price),
    ):
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"{name} must be positive and finite")
    if atr is not None and (not math.isfinite(atr) or atr <= 0.0):
        raise ValueError("ATR must be positive and finite when provided")
    if execution_buffer_override is not None and (
        not math.isfinite(execution_buffer_override) or execution_buffer_override < 0.0
    ):
        raise ValueError("execution buffer override must be finite and non-negative")

    percentage_buffer = preferred_entry * minimum_buffer_pct / 100.0
    if execution_buffer_override is not None:
        buffer = execution_buffer_override
        reason = (
            "strategy buffer topped up to the single shared runtime ATR/spread floor"
            if invalidation_already_buffered and buffer > 0.0
            else "strategy invalidation already satisfies the single shared noise floor"
            if invalidation_already_buffered
            else "single shared runtime ATR/spread execution buffer"
        )
    elif invalidation_already_buffered:
        buffer = 0.0
        reason = "strategy invalidation already includes the single noise buffer"
    elif invalidation_type is InvalidationType.VOLATILITY:
        buffer = percentage_buffer
        reason = f"single minimum {minimum_buffer_pct:g}% execution buffer"
    else:
        if atr is None:
            atr_buffer = 0.0
            volatility_band = "unavailable"
            effective_ratio = structural_buffer_atr
        else:
            effective_ratio, volatility_band = _adaptive_structural_buffer_atr(
                preferred_entry=preferred_entry,
                atr=atr,
                configured_floor=structural_buffer_atr,
            )
            atr_buffer = atr * effective_ratio
        buffer = max(percentage_buffer, atr_buffer)
        reason = (
            f"single {effective_ratio:g} ATR symbol-relative {volatility_band}-volatility "
            "structural-noise buffer"
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
    tick_size: float | None = None,
) -> tuple[TargetLevel, ...]:
    """Normalize defensible strategy targets using canonical hierarchy."""

    if not strategy_targets:
        raise ValueError("at least one strategy target is required")
    if not math.isfinite(preferred_entry) or preferred_entry <= 0.0:
        raise ValueError("preferred entry must be positive and finite")
    if not math.isfinite(stop_price) or stop_price <= 0.0:
        raise ValueError("stop price must be positive and finite")
    if math.isclose(preferred_entry, stop_price, rel_tol=0.0, abs_tol=0.0):
        raise ValueError("stop must differ from preferred entry")
    if tick_size is not None and (not math.isfinite(tick_size) or tick_size <= 0.0):
        raise ValueError("tick size must be positive and finite when provided")

    directionally_valid = tuple(
        level
        for level in strategy_targets
        if _target_is_directionally_valid(
            direction=direction,
            preferred_entry=preferred_entry,
            target_price=level.price,
        )
    )
    if not directionally_valid:
        raise ValueError("at least one directionally valid target is required")

    source_ordered = tuple(
        sorted(
            directionally_valid,
            key=lambda level: (
                _TARGET_SOURCE_PRIORITY[level.kind],
                abs(level.price - preferred_entry),
                level.price,
                level.label,
            ),
        )
    )
    deduplicated = _deduplicate_targets(source_ordered, tick_size=tick_size)
    price_ordered = tuple(
        sorted(
            deduplicated,
            key=lambda level: abs(level.price - preferred_entry),
        )
    )

    return tuple(
        TargetLevel(
            kind=level.kind,
            price=level.price,
            label=f"TP{index}",
            rationale=level.rationale,
        )
        for index, level in enumerate(price_ordered[:3], start=1)
    )


def _target_is_directionally_valid(
    *,
    direction: TradeDirection,
    preferred_entry: float,
    target_price: float,
) -> bool:
    if direction is TradeDirection.LONG:
        return target_price > preferred_entry
    return target_price < preferred_entry


def _deduplicate_targets(
    targets: tuple[TargetLevel, ...],
    *,
    tick_size: float | None,
) -> tuple[TargetLevel, ...]:
    retained: list[TargetLevel] = []
    for target in targets:
        if not any(
            _same_target_price(
                target.price,
                existing.price,
                tick_size=tick_size,
            )
            for existing in retained
        ):
            retained.append(target)
    return tuple(retained)


def _same_target_price(
    left: float,
    right: float,
    *,
    tick_size: float | None,
) -> bool:
    tolerance = max(abs(left), abs(right), 1.0) * 1e-12 if tick_size is None else tick_size
    return math.isclose(left, right, rel_tol=0.0, abs_tol=tolerance)


__all__ = [
    "StopGeometry",
    "TargetSourcePriority",
    "build_layered_targets",
    "build_stop_geometry",
]
