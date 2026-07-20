"""Read-only liquidation-impulse diagnostics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.strategies.contracts import TradeDirection


class LiquidationImpulseState(StrEnum):
    """Directional state derived from long/short forced-liquidation notional."""

    SUPPORTIVE = "supportive"
    NEUTRAL = "neutral"
    CONTRADICTORY = "contradictory"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class LiquidationImpulsePolicy:
    """Thresholds for interpreting directional liquidation imbalance."""

    minimum_total_notional: float = 1.0
    supportive_ratio: float = 0.20
    contradictory_ratio: float = 0.20

    def __post_init__(self) -> None:
        if not math.isfinite(self.minimum_total_notional) or self.minimum_total_notional < 0:
            raise ValueError("minimum total notional must be finite and non-negative")
        for name, value in (
            ("supportive ratio", self.supportive_ratio),
            ("contradictory ratio", self.contradictory_ratio),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between zero and one")


@dataclass(frozen=True, slots=True)
class LiquidationImpulseObservation:
    """Normalized forced-liquidation totals over one synchronized window."""

    long_liquidation_notional: float
    short_liquidation_notional: float
    event_count: int
    window_seconds: int

    def __post_init__(self) -> None:
        for name, value in (
            ("long liquidation notional", self.long_liquidation_notional),
            ("short liquidation notional", self.short_liquidation_notional),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.event_count < 0:
            raise ValueError("event count cannot be negative")
        if self.window_seconds <= 0:
            raise ValueError("window seconds must be positive")


@dataclass(frozen=True, slots=True)
class LiquidationImpulseAudit:
    """Read-only directional liquidation assessment."""

    direction: TradeDirection
    state: LiquidationImpulseState
    signed_imbalance_ratio: float
    total_notional: float
    event_count: int
    window_seconds: int

    @property
    def usable(self) -> bool:
        return self.state is not LiquidationImpulseState.INSUFFICIENT


def audit_liquidation_impulse(
    direction: TradeDirection,
    observation: LiquidationImpulseObservation,
    *,
    policy: LiquidationImpulsePolicy,
) -> LiquidationImpulseAudit:
    """Classify forced-liquidation flow relative to the proposed direction."""

    total = observation.long_liquidation_notional + observation.short_liquidation_notional
    if total < policy.minimum_total_notional or observation.event_count == 0:
        return LiquidationImpulseAudit(
            direction=direction,
            state=LiquidationImpulseState.INSUFFICIENT,
            signed_imbalance_ratio=0.0,
            total_notional=total,
            event_count=observation.event_count,
            window_seconds=observation.window_seconds,
        )

    raw_ratio = (
        observation.short_liquidation_notional - observation.long_liquidation_notional
    ) / total
    signed_ratio = raw_ratio if direction is TradeDirection.LONG else -raw_ratio
    if signed_ratio >= policy.supportive_ratio:
        state = LiquidationImpulseState.SUPPORTIVE
    elif signed_ratio <= -policy.contradictory_ratio:
        state = LiquidationImpulseState.CONTRADICTORY
    else:
        state = LiquidationImpulseState.NEUTRAL

    return LiquidationImpulseAudit(
        direction=direction,
        state=state,
        signed_imbalance_ratio=signed_ratio,
        total_notional=total,
        event_count=observation.event_count,
        window_seconds=observation.window_seconds,
    )


__all__ = [
    "LiquidationImpulseAudit",
    "LiquidationImpulseObservation",
    "LiquidationImpulsePolicy",
    "LiquidationImpulseState",
    "audit_liquidation_impulse",
]
