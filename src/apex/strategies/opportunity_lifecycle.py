"""Read-only lifecycle diagnostics for candidate entry opportunities."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.strategies.contracts import TradeCandidate, TradeDirection


class OpportunityStage(StrEnum):
    """Diagnostic stage of one candidate opportunity."""

    CMP = "cmp"
    DEVELOPING = "developing"
    ARMED = "armed"
    MISSED = "missed"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class LifecycleReason(StrEnum):
    """Machine-readable reason for a lifecycle stage."""

    PRICE_INSIDE_ENTRY_ZONE = "price_inside_entry_zone"
    PRICE_APPROACHING_ENTRY = "price_approaching_entry"
    PRICE_REACHED_TRIGGER = "price_reached_trigger"
    PRICE_PASSED_MAX_CHASE = "price_passed_max_chase"
    STRUCTURE_INVALIDATED = "structure_invalidated"
    TIME_BUDGET_EXHAUSTED = "time_budget_exhausted"
    BAR_BUDGET_EXHAUSTED = "bar_budget_exhausted"


@dataclass(frozen=True, slots=True)
class OpportunityLifecyclePolicy:
    """Explicit thresholds for lifecycle classification."""

    approaching_distance: float
    armed_distance: float = 0.0

    def __post_init__(self) -> None:
        values = (self.approaching_distance, self.armed_distance)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("lifecycle distances must be finite")
        if self.approaching_distance < 0:
            raise ValueError("approaching distance cannot be negative")
        if self.armed_distance < 0:
            raise ValueError("armed distance cannot be negative")
        if self.armed_distance > self.approaching_distance:
            raise ValueError("armed distance cannot exceed approaching distance")


@dataclass(frozen=True, slots=True)
class OpportunityLifecycleObservation:
    """Current market and age inputs for lifecycle evaluation."""

    current_price: float
    elapsed_seconds: int
    elapsed_bars: int

    def __post_init__(self) -> None:
        if not math.isfinite(self.current_price) or self.current_price <= 0:
            raise ValueError("current price must be positive and finite")
        if self.elapsed_seconds < 0:
            raise ValueError("elapsed seconds cannot be negative")
        if self.elapsed_bars < 0:
            raise ValueError("elapsed bars cannot be negative")


@dataclass(frozen=True, slots=True)
class OpportunityLifecycleAudit:
    """Read-only lifecycle classification for one candidate."""

    symbol: str
    direction: TradeDirection
    previous_stage: OpportunityStage | None
    stage: OpportunityStage
    reasons: tuple[LifecycleReason, ...]
    distance_to_zone: float
    elapsed_seconds: int
    elapsed_bars: int

    @property
    def terminal(self) -> bool:
        return self.stage in (
            OpportunityStage.MISSED,
            OpportunityStage.INVALIDATED,
            OpportunityStage.EXPIRED,
        )


def _distance_to_zone(candidate: TradeCandidate, price: float) -> float:
    if candidate.entry.lower <= price <= candidate.entry.upper:
        return 0.0
    if price < candidate.entry.lower:
        return candidate.entry.lower - price
    return price - candidate.entry.upper


def _structure_invalidated(candidate: TradeCandidate, price: float) -> bool:
    if candidate.direction is TradeDirection.LONG:
        return price <= candidate.invalidation.price
    return price >= candidate.invalidation.price


def _passed_max_chase(candidate: TradeCandidate, price: float) -> bool:
    max_chase = candidate.entry.max_chase_price
    if max_chase is None:
        return False
    if candidate.direction is TradeDirection.LONG:
        return price > max_chase
    return price < max_chase


def audit_opportunity_lifecycle(
    candidate: TradeCandidate,
    observation: OpportunityLifecycleObservation,
    *,
    policy: OpportunityLifecyclePolicy,
    previous_stage: OpportunityStage | None = None,
) -> OpportunityLifecycleAudit:
    """Classify lifecycle stage without mutating candidate state."""

    lifecycle = candidate.lifecycle
    if lifecycle is None:
        raise ValueError("candidate lifecycle is required")

    distance = _distance_to_zone(candidate, observation.current_price)
    reasons: list[LifecycleReason] = []

    if _structure_invalidated(candidate, observation.current_price):
        stage = OpportunityStage.INVALIDATED
        reasons.append(LifecycleReason.STRUCTURE_INVALIDATED)
    elif observation.elapsed_seconds >= lifecycle.expires_after_seconds:
        stage = OpportunityStage.EXPIRED
        reasons.append(LifecycleReason.TIME_BUDGET_EXHAUSTED)
    elif observation.elapsed_bars >= lifecycle.expires_after_bars:
        stage = OpportunityStage.EXPIRED
        reasons.append(LifecycleReason.BAR_BUDGET_EXHAUSTED)
    elif _passed_max_chase(candidate, observation.current_price):
        stage = OpportunityStage.MISSED
        reasons.append(LifecycleReason.PRICE_PASSED_MAX_CHASE)
    elif candidate.entry.lower <= observation.current_price <= candidate.entry.upper:
        stage = OpportunityStage.CMP
        reasons.append(LifecycleReason.PRICE_INSIDE_ENTRY_ZONE)
    elif distance <= policy.armed_distance or distance <= policy.approaching_distance:
        stage = OpportunityStage.ARMED
        reasons.append(LifecycleReason.PRICE_REACHED_TRIGGER)
    else:
        stage = OpportunityStage.DEVELOPING
        reasons.append(LifecycleReason.PRICE_APPROACHING_ENTRY)

    return OpportunityLifecycleAudit(
        symbol=candidate.symbol,
        direction=candidate.direction,
        previous_stage=previous_stage,
        stage=stage,
        reasons=tuple(reasons),
        distance_to_zone=distance,
        elapsed_seconds=observation.elapsed_seconds,
        elapsed_bars=observation.elapsed_bars,
    )


__all__ = [
    "LifecycleReason",
    "OpportunityLifecycleAudit",
    "OpportunityLifecycleObservation",
    "OpportunityLifecyclePolicy",
    "OpportunityStage",
    "audit_opportunity_lifecycle",
]
