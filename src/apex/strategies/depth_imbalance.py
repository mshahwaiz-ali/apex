"""Read-only order-book depth imbalance diagnostics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.strategies.contracts import TradeDirection


class DepthImbalanceState(StrEnum):
    """Directional state derived from near-touch bid/ask depth."""

    SUPPORTIVE = "supportive"
    NEUTRAL = "neutral"
    CONTRADICTORY = "contradictory"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class DepthImbalancePolicy:
    """Thresholds for interpreting synchronized near-touch depth."""

    minimum_total_notional: float = 1.0
    supportive_ratio: float = 0.15
    contradictory_ratio: float = 0.15

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
class DepthImbalanceObservation:
    """Normalized near-touch depth totals for one synchronized snapshot."""

    bid_notional: float
    ask_notional: float
    levels_per_side: int
    window_basis_points: float

    def __post_init__(self) -> None:
        for name, value in (
            ("bid notional", self.bid_notional),
            ("ask notional", self.ask_notional),
            ("window basis points", self.window_basis_points),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.levels_per_side <= 0:
            raise ValueError("levels per side must be positive")
        if self.window_basis_points <= 0:
            raise ValueError("window basis points must be positive")


@dataclass(frozen=True, slots=True)
class DepthImbalanceAudit:
    """Read-only directional depth assessment."""

    direction: TradeDirection
    state: DepthImbalanceState
    signed_imbalance_ratio: float
    total_notional: float
    levels_per_side: int
    window_basis_points: float

    @property
    def usable(self) -> bool:
        return self.state is not DepthImbalanceState.INSUFFICIENT


def audit_depth_imbalance(
    direction: TradeDirection,
    observation: DepthImbalanceObservation,
    *,
    policy: DepthImbalancePolicy,
) -> DepthImbalanceAudit:
    """Classify near-touch depth relative to the proposed direction."""

    total = observation.bid_notional + observation.ask_notional
    if total < policy.minimum_total_notional:
        return DepthImbalanceAudit(
            direction=direction,
            state=DepthImbalanceState.INSUFFICIENT,
            signed_imbalance_ratio=0.0,
            total_notional=total,
            levels_per_side=observation.levels_per_side,
            window_basis_points=observation.window_basis_points,
        )

    raw_ratio = (observation.bid_notional - observation.ask_notional) / total
    signed_ratio = raw_ratio if direction is TradeDirection.LONG else -raw_ratio
    if signed_ratio >= policy.supportive_ratio:
        state = DepthImbalanceState.SUPPORTIVE
    elif signed_ratio <= -policy.contradictory_ratio:
        state = DepthImbalanceState.CONTRADICTORY
    else:
        state = DepthImbalanceState.NEUTRAL

    return DepthImbalanceAudit(
        direction=direction,
        state=state,
        signed_imbalance_ratio=signed_ratio,
        total_notional=total,
        levels_per_side=observation.levels_per_side,
        window_basis_points=observation.window_basis_points,
    )


__all__ = [
    "DepthImbalanceAudit",
    "DepthImbalanceObservation",
    "DepthImbalancePolicy",
    "DepthImbalanceState",
    "audit_depth_imbalance",
]
