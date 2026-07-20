"""Read-only comparison diagnostics for an original plan and current evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.strategies.contracts import (
    StrategyEvidence,
    TradeCandidate,
    TradeDirection,
)
from apex.strategies.opportunity_lifecycle import OpportunityStage
from apex.strategies.opportunity_runner import RunnerLifecycleAudit


class PlanComparisonStatus(StrEnum):
    """High-level relationship between the original plan and current state."""

    UNCHANGED = "unchanged"
    PROGRESSED = "progressed"
    DEGRADED = "degraded"
    TERMINAL = "terminal"


class PlanChangeKind(StrEnum):
    """Machine-readable changes observed since the original plan."""

    LIFECYCLE_CHANGED = "lifecycle_changed"
    TARGET_ACHIEVED = "target_achieved"
    SUPPORT_ADDED = "support_added"
    SUPPORT_REMOVED = "support_removed"
    CONTRADICTION_ADDED = "contradiction_added"
    CONTRADICTION_REMOVED = "contradiction_removed"
    RUNNER_HOLD = "runner_hold"
    RUNNER_TIGHTEN = "runner_tighten"
    RUNNER_EXIT = "runner_exit"


@dataclass(frozen=True, slots=True)
class OriginalPlanSnapshot:
    """Stable, immutable snapshot derived from an original candidate plan."""

    setup_id: str
    symbol: str
    direction: TradeDirection
    captured_at: datetime
    entry_lower: float
    entry_upper: float
    preferred_entry: float
    structural_invalidation: float
    targets: tuple[float, ...]
    evidence: StrategyEvidence
    lifecycle_stage: OpportunityStage

    def __post_init__(self) -> None:
        if not self.setup_id.strip():
            raise ValueError("setup id cannot be empty")
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("captured time must be timezone-aware")
        prices = (
            self.entry_lower,
            self.entry_upper,
            self.preferred_entry,
            self.structural_invalidation,
            *self.targets,
        )
        if not all(math.isfinite(price) and price > 0 for price in prices):
            raise ValueError("snapshot prices must be positive and finite")
        if self.entry_lower > self.entry_upper:
            raise ValueError("entry lower cannot exceed entry upper")
        if not self.entry_lower <= self.preferred_entry <= self.entry_upper:
            raise ValueError("preferred entry must lie inside the entry zone")
        if not self.targets:
            raise ValueError("snapshot requires at least one target")


@dataclass(frozen=True, slots=True)
class CurrentPlanObservation:
    """Current lifecycle, evidence, target, and runner observations."""

    lifecycle_stage: OpportunityStage
    achieved_target_labels: tuple[str, ...]
    evidence: StrategyEvidence
    runner: RunnerLifecycleAudit | None = None

    def __post_init__(self) -> None:
        if len(set(self.achieved_target_labels)) != len(self.achieved_target_labels):
            raise ValueError("achieved target labels must be unique")


@dataclass(frozen=True, slots=True)
class PlanChange:
    """One deterministic change between original and current plan state."""

    kind: PlanChangeKind
    detail: str

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("plan change detail cannot be empty")


@dataclass(frozen=True, slots=True)
class OriginalPlanComparisonAudit:
    """Read-only comparison result for one stable setup identity."""

    setup_id: str
    symbol: str
    direction: TradeDirection
    status: PlanComparisonStatus
    original_stage: OpportunityStage
    current_stage: OpportunityStage
    achieved_target_labels: tuple[str, ...]
    added_support: tuple[str, ...]
    removed_support: tuple[str, ...]
    added_contradictions: tuple[str, ...]
    removed_contradictions: tuple[str, ...]
    changes: tuple[PlanChange, ...]
    runner: RunnerLifecycleAudit | None


def snapshot_original_plan(
    candidate: TradeCandidate,
    *,
    setup_id: str | None = None,
    lifecycle_stage: OpportunityStage = OpportunityStage.DEVELOPING,
) -> OriginalPlanSnapshot:
    """Create a stable diagnostic snapshot without mutating the candidate."""

    lifecycle = candidate.lifecycle
    if lifecycle is None:
        raise ValueError("candidate lifecycle is required for plan snapshot")
    resolved_setup_id = setup_id or lifecycle.cooldown_key
    return OriginalPlanSnapshot(
        setup_id=resolved_setup_id,
        symbol=candidate.symbol,
        direction=candidate.direction,
        captured_at=candidate.decision_time,
        entry_lower=candidate.entry.lower,
        entry_upper=candidate.entry.upper,
        preferred_entry=candidate.entry.preferred,
        structural_invalidation=candidate.invalidation.price,
        targets=tuple(level.price for level in candidate.targets.levels),
        evidence=candidate.evidence,
        lifecycle_stage=lifecycle_stage,
    )


def _sorted_difference(
    left: tuple[str, ...],
    right: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(sorted(set(left) - set(right)))


def _runner_change(runner: RunnerLifecycleAudit) -> PlanChange:
    decision = runner.decision.value
    if decision == "hold_runner":
        kind = PlanChangeKind.RUNNER_HOLD
    elif decision == "tighten_and_hold":
        kind = PlanChangeKind.RUNNER_TIGHTEN
    else:
        kind = PlanChangeKind.RUNNER_EXIT
    return PlanChange(kind=kind, detail=f"runner decision: {decision}")


def _comparison_status(
    observation: CurrentPlanObservation,
    *,
    changes: tuple[PlanChange, ...],
    added_contradictions: tuple[str, ...],
    removed_support: tuple[str, ...],
) -> PlanComparisonStatus:
    if observation.lifecycle_stage in {
        OpportunityStage.MISSED,
        OpportunityStage.INVALIDATED,
        OpportunityStage.EXPIRED,
    }:
        return PlanComparisonStatus.TERMINAL
    if added_contradictions or removed_support:
        return PlanComparisonStatus.DEGRADED
    if observation.achieved_target_labels or observation.runner is not None:
        return PlanComparisonStatus.PROGRESSED
    if changes:
        return PlanComparisonStatus.PROGRESSED
    return PlanComparisonStatus.UNCHANGED


def audit_original_plan_comparison(
    original: OriginalPlanSnapshot,
    observation: CurrentPlanObservation,
) -> OriginalPlanComparisonAudit:
    """Compare current evidence and lifecycle against an original snapshot."""

    added_support = _sorted_difference(
        observation.evidence.supporting,
        original.evidence.supporting,
    )
    removed_support = _sorted_difference(
        original.evidence.supporting,
        observation.evidence.supporting,
    )
    added_contradictions = _sorted_difference(
        observation.evidence.contradictions,
        original.evidence.contradictions,
    )
    removed_contradictions = _sorted_difference(
        original.evidence.contradictions,
        observation.evidence.contradictions,
    )

    changes: list[PlanChange] = []
    if observation.lifecycle_stage is not original.lifecycle_stage:
        changes.append(
            PlanChange(
                kind=PlanChangeKind.LIFECYCLE_CHANGED,
                detail=(
                    f"lifecycle: {original.lifecycle_stage.value} -> "
                    f"{observation.lifecycle_stage.value}"
                ),
            )
        )
    for label in observation.achieved_target_labels:
        changes.append(
            PlanChange(
                kind=PlanChangeKind.TARGET_ACHIEVED,
                detail=f"target achieved: {label}",
            )
        )
    for value in added_support:
        changes.append(
            PlanChange(
                kind=PlanChangeKind.SUPPORT_ADDED,
                detail=f"support added: {value}",
            )
        )
    for value in removed_support:
        changes.append(
            PlanChange(
                kind=PlanChangeKind.SUPPORT_REMOVED,
                detail=f"support removed: {value}",
            )
        )
    for value in added_contradictions:
        changes.append(
            PlanChange(
                kind=PlanChangeKind.CONTRADICTION_ADDED,
                detail=f"contradiction added: {value}",
            )
        )
    for value in removed_contradictions:
        changes.append(
            PlanChange(
                kind=PlanChangeKind.CONTRADICTION_REMOVED,
                detail=f"contradiction removed: {value}",
            )
        )
    if observation.runner is not None:
        changes.append(_runner_change(observation.runner))

    change_tuple = tuple(changes)
    return OriginalPlanComparisonAudit(
        setup_id=original.setup_id,
        symbol=original.symbol,
        direction=original.direction,
        status=_comparison_status(
            observation,
            changes=change_tuple,
            added_contradictions=added_contradictions,
            removed_support=removed_support,
        ),
        original_stage=original.lifecycle_stage,
        current_stage=observation.lifecycle_stage,
        achieved_target_labels=observation.achieved_target_labels,
        added_support=added_support,
        removed_support=removed_support,
        added_contradictions=added_contradictions,
        removed_contradictions=removed_contradictions,
        changes=change_tuple,
        runner=observation.runner,
    )


__all__ = [
    "CurrentPlanObservation",
    "OriginalPlanComparisonAudit",
    "OriginalPlanSnapshot",
    "PlanChange",
    "PlanChangeKind",
    "PlanComparisonStatus",
    "audit_original_plan_comparison",
    "snapshot_original_plan",
]
