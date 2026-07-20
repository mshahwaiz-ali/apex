"""Read-only post-TP runner lifecycle diagnostics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.strategies.contracts import TradeCandidate, TradeDirection


class RunnerDecision(StrEnum):
    """Diagnostic decision for the remaining position after TP1."""

    HOLD_RUNNER = "hold_runner"
    TIGHTEN_AND_HOLD = "tighten_and_hold"
    EXIT_REMAINDER = "exit_remainder"


class RunnerReason(StrEnum):
    """Machine-readable reasons supporting a runner decision."""

    STRUCTURE_BROKEN_3M = "structure_broken_3m"
    STRUCTURE_BROKEN_5M = "structure_broken_5m"
    OPPOSITE_RECLAIM = "opposite_reclaim"
    MOMENTUM_REVERSAL_CONFIRMED = "momentum_reversal_confirmed"
    STAGNATION_EXPIRED = "stagnation_expired"
    THESIS_BROKEN_15M = "thesis_broken_15m"
    STRONG_OPPOSING_ABSORPTION = "strong_opposing_absorption"
    MOMENTUM_SLOWING = "momentum_slowing"
    OPPOSING_STRUCTURE_NEAR = "opposing_structure_near"
    FLOW_MIXED = "flow_mixed"
    CONTINUATION_VOLUME_WEAK = "continuation_volume_weak"
    VWAP_OR_EMA_LOST = "vwap_or_ema_lost"
    TARGET_ROOM_REDUCED = "target_room_reduced"
    STRUCTURE_INTACT = "structure_intact"
    CONTINUATION_HEALTHY = "continuation_healthy"
    TARGET_ROOM_AVAILABLE = "target_room_available"


@dataclass(frozen=True, slots=True)
class RunnerObservation:
    """Objective post-TP evidence used by the diagnostic evaluator."""

    structure_intact_3m: bool
    structure_intact_5m: bool
    opposite_reclaim: bool
    continuation_volume_healthy: bool
    correct_side_vwap_or_ema: bool
    target_room_remaining: bool
    strong_opposing_absorption: bool
    thesis_intact_15m: bool
    momentum_slowing: bool = False
    opposing_structure_near: bool = False
    flow_mixed: bool = False
    momentum_reversal_confirmed: bool = False
    stagnation_expired: bool = False
    protect_reference: float | None = None

    def __post_init__(self) -> None:
        if self.protect_reference is not None and (
            not math.isfinite(self.protect_reference) or self.protect_reference <= 0
        ):
            raise ValueError("protect reference must be positive and finite")


@dataclass(frozen=True, slots=True)
class RunnerLifecycleAudit:
    """Read-only runner decision that does not mutate the candidate."""

    symbol: str
    direction: TradeDirection
    decision: RunnerDecision
    reasons: tuple[RunnerReason, ...]
    protect_reference: float | None

    @property
    def requires_exit(self) -> bool:
        return self.decision is RunnerDecision.EXIT_REMAINDER

    @property
    def requires_tightening(self) -> bool:
        return self.decision is RunnerDecision.TIGHTEN_AND_HOLD


def _exit_reasons(observation: RunnerObservation) -> tuple[RunnerReason, ...]:
    reasons: list[RunnerReason] = []
    if not observation.structure_intact_3m:
        reasons.append(RunnerReason.STRUCTURE_BROKEN_3M)
    if not observation.structure_intact_5m:
        reasons.append(RunnerReason.STRUCTURE_BROKEN_5M)
    if observation.opposite_reclaim:
        reasons.append(RunnerReason.OPPOSITE_RECLAIM)
    if observation.momentum_reversal_confirmed:
        reasons.append(RunnerReason.MOMENTUM_REVERSAL_CONFIRMED)
    if observation.stagnation_expired:
        reasons.append(RunnerReason.STAGNATION_EXPIRED)
    if not observation.thesis_intact_15m:
        reasons.append(RunnerReason.THESIS_BROKEN_15M)
    if observation.strong_opposing_absorption:
        reasons.append(RunnerReason.STRONG_OPPOSING_ABSORPTION)
    return tuple(reasons)


def _tighten_reasons(observation: RunnerObservation) -> tuple[RunnerReason, ...]:
    reasons: list[RunnerReason] = []
    if observation.momentum_slowing:
        reasons.append(RunnerReason.MOMENTUM_SLOWING)
    if observation.opposing_structure_near:
        reasons.append(RunnerReason.OPPOSING_STRUCTURE_NEAR)
    if observation.flow_mixed:
        reasons.append(RunnerReason.FLOW_MIXED)
    if not observation.continuation_volume_healthy:
        reasons.append(RunnerReason.CONTINUATION_VOLUME_WEAK)
    if not observation.correct_side_vwap_or_ema:
        reasons.append(RunnerReason.VWAP_OR_EMA_LOST)
    if not observation.target_room_remaining:
        reasons.append(RunnerReason.TARGET_ROOM_REDUCED)
    return tuple(reasons)


def audit_runner_lifecycle(
    candidate: TradeCandidate,
    observation: RunnerObservation,
) -> RunnerLifecycleAudit:
    """Evaluate post-TP runner state without changing candidate or position state."""

    exit_reasons = _exit_reasons(observation)
    if exit_reasons:
        return RunnerLifecycleAudit(
            symbol=candidate.symbol,
            direction=candidate.direction,
            decision=RunnerDecision.EXIT_REMAINDER,
            reasons=exit_reasons,
            protect_reference=None,
        )

    tighten_reasons = _tighten_reasons(observation)
    if tighten_reasons:
        if observation.protect_reference is None:
            raise ValueError("tighten-and-hold decision requires a protect reference")
        return RunnerLifecycleAudit(
            symbol=candidate.symbol,
            direction=candidate.direction,
            decision=RunnerDecision.TIGHTEN_AND_HOLD,
            reasons=tighten_reasons,
            protect_reference=observation.protect_reference,
        )

    return RunnerLifecycleAudit(
        symbol=candidate.symbol,
        direction=candidate.direction,
        decision=RunnerDecision.HOLD_RUNNER,
        reasons=(
            RunnerReason.STRUCTURE_INTACT,
            RunnerReason.CONTINUATION_HEALTHY,
            RunnerReason.TARGET_ROOM_AVAILABLE,
        ),
        protect_reference=observation.protect_reference,
    )


__all__ = [
    "RunnerDecision",
    "RunnerLifecycleAudit",
    "RunnerObservation",
    "RunnerReason",
    "audit_runner_lifecycle",
]
