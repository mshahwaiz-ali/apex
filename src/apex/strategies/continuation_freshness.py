"""Objective continuation freshness and extension measurements."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.domain.models import Candle
from apex.strategies.context import FeatureSnapshot
from apex.strategies.contracts import TradeDirection


class ContinuationState(StrEnum):
    """Freshness state for a directional continuation thesis."""

    FRESH_BREAK = "fresh_break"
    FIRST_CONTINUATION = "first_continuation"
    MATURE_CONTINUATION = "mature_continuation"
    EXHAUSTED = "exhausted"


@dataclass(frozen=True, slots=True)
class ContinuationFreshness:
    """Measured continuation freshness without granting execution permission."""

    state: ContinuationState
    impulse_travel_atr: float
    objective_consumption: float
    remaining_target_room_atr: float
    ema_extension_atr: float | None
    vwap_extension_atr: float | None
    momentum_decelerating: bool
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        for name, value in (
            ("impulse travel ATR", self.impulse_travel_atr),
            ("objective consumption", self.objective_consumption),
            ("remaining target room ATR", self.remaining_target_room_atr),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be non-negative and finite")
        if self.objective_consumption > 1:
            raise ValueError("objective consumption cannot exceed one")
        optional_measurements: tuple[tuple[str, float | None], ...] = (
            ("EMA extension ATR", self.ema_extension_atr),
            ("VWAP extension ATR", self.vwap_extension_atr),
        )
        for name, optional_value in optional_measurements:
            if optional_value is not None and (
                not math.isfinite(optional_value) or optional_value < 0
            ):
                raise ValueError(f"{name} must be non-negative and finite")
        if not self.reasons:
            raise ValueError("continuation freshness requires explanatory reasons")

    @property
    def allows_new_continuation(self) -> bool:
        return self.state is not ContinuationState.EXHAUSTED

    @property
    def requires_conditional_entry(self) -> bool:
        return self.state is ContinuationState.MATURE_CONTINUATION


def measure_continuation_freshness(
    *,
    candles: tuple[Candle, ...],
    features: FeatureSnapshot,
    direction: TradeDirection,
    current_price: float,
    impulse_origin: float,
    target_price: float,
) -> ContinuationFreshness:
    """Measure how much directional movement has occurred and remains."""

    if not candles:
        raise ValueError("continuation freshness requires candle history")
    for name, value in (
        ("current price", current_price),
        ("impulse origin", impulse_origin),
        ("target price", target_price),
    ):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be positive and finite")

    bullish = direction is TradeDirection.LONG
    total_objective = target_price - impulse_origin if bullish else impulse_origin - target_price
    travelled = current_price - impulse_origin if bullish else impulse_origin - current_price
    remaining = target_price - current_price if bullish else current_price - target_price
    if total_objective <= 0:
        raise ValueError("target must be beyond impulse origin in the trade direction")

    atr = features.atr
    impulse_travel_atr = max(0.0, travelled / atr)
    objective_consumption = min(1.0, max(0.0, travelled / total_objective))
    remaining_target_room_atr = max(0.0, remaining / atr)
    ema_extension_atr = _reference_extension(
        current_price=current_price,
        reference=features.ema_fast,
        atr=atr,
        bullish=bullish,
    )
    vwap_extension_atr = _reference_extension(
        current_price=current_price,
        reference=features.vwap,
        atr=atr,
        bullish=bullish,
    )
    momentum_decelerating = _momentum_decelerating(candles, bullish=bullish)

    state = _classify_state(
        impulse_travel_atr=impulse_travel_atr,
        objective_consumption=objective_consumption,
        remaining_target_room_atr=remaining_target_room_atr,
        ema_extension_atr=ema_extension_atr,
        vwap_extension_atr=vwap_extension_atr,
        momentum_decelerating=momentum_decelerating,
    )
    reasons = (
        f"impulse travelled {impulse_travel_atr:.2f} ATR",
        f"{objective_consumption:.0%} of the measured objective is consumed",
        f"{remaining_target_room_atr:.2f} ATR remains to the objective",
        (
            "recent candle bodies show directional deceleration"
            if momentum_decelerating
            else "recent candle bodies do not show directional deceleration"
        ),
    )
    return ContinuationFreshness(
        state=state,
        impulse_travel_atr=impulse_travel_atr,
        objective_consumption=objective_consumption,
        remaining_target_room_atr=remaining_target_room_atr,
        ema_extension_atr=ema_extension_atr,
        vwap_extension_atr=vwap_extension_atr,
        momentum_decelerating=momentum_decelerating,
        reasons=reasons,
    )


def _reference_extension(
    *,
    current_price: float,
    reference: float | None,
    atr: float,
    bullish: bool,
) -> float | None:
    if reference is None:
        return None
    directional_distance = current_price - reference if bullish else reference - current_price
    return max(0.0, directional_distance / atr)


def _momentum_decelerating(candles: tuple[Candle, ...], *, bullish: bool) -> bool:
    closed = tuple(candle for candle in candles if candle.is_closed)
    if len(closed) < 3:
        return False
    recent = closed[-3:]
    directional_bodies = tuple(
        max(0.0, candle.close - candle.open) if bullish else max(0.0, candle.open - candle.close)
        for candle in recent
    )
    return (
        directional_bodies[0] > directional_bodies[1] > directional_bodies[2]
        and directional_bodies[2] > 0
    )


def _classify_state(
    *,
    impulse_travel_atr: float,
    objective_consumption: float,
    remaining_target_room_atr: float,
    ema_extension_atr: float | None,
    vwap_extension_atr: float | None,
    momentum_decelerating: bool,
) -> ContinuationState:
    reference_extension = max(
        value for value in (ema_extension_atr, vwap_extension_atr, 0.0) if value is not None
    )
    if (
        objective_consumption >= 0.85
        or remaining_target_room_atr < 0.50
        or (impulse_travel_atr >= 2.5 and reference_extension >= 1.5 and momentum_decelerating)
    ):
        return ContinuationState.EXHAUSTED
    if objective_consumption >= 0.60 or impulse_travel_atr >= 2.0 or reference_extension >= 1.25:
        return ContinuationState.MATURE_CONTINUATION
    if impulse_travel_atr >= 0.75 or objective_consumption >= 0.25:
        return ContinuationState.FIRST_CONTINUATION
    return ContinuationState.FRESH_BREAK


__all__ = [
    "ContinuationFreshness",
    "ContinuationState",
    "measure_continuation_freshness",
]
