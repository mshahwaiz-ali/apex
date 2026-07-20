"""Read-only composition diagnostics for collision, sequence, and lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.strategies.contracts import TradeCandidate
from apex.strategies.opportunity_collision import (
    CollisionResolutionAudit,
    CollisionResolutionPolicy,
    OpportunityCollisionAudit,
    OpportunitySequenceAudit,
    OpportunitySequencePolicy,
    audit_cmp_collision,
    audit_collision_resolution,
    audit_opportunity_sequence,
)
from apex.strategies.opportunity_lifecycle import (
    OpportunityLifecycleAudit,
    OpportunityLifecycleObservation,
    OpportunityLifecyclePolicy,
    OpportunityStage,
    audit_opportunity_lifecycle,
)


class TransitionDisposition(StrEnum):
    """Diagnostic legality of one lifecycle-stage transition."""

    INITIAL = "initial"
    LEGAL = "legal"
    ILLEGAL = "illegal"


class TransitionReason(StrEnum):
    """Machine-readable reason for a transition decision."""

    NO_PREVIOUS_STAGE = "no_previous_stage"
    SAME_STAGE = "same_stage"
    ACTIVE_STAGE_MOVEMENT = "active_stage_movement"
    ACTIVE_TO_TERMINAL = "active_to_terminal"
    TERMINAL_STATE_RETAINED = "terminal_state_retained"
    TERMINAL_PRECEDENCE_ADVANCED = "terminal_precedence_advanced"
    TERMINAL_REACTIVATION_BLOCKED = "terminal_reactivation_blocked"
    INVALIDATED_STATE_CHANGED = "invalidated_state_changed"


_ACTIVE_STAGES = frozenset(
    {
        OpportunityStage.DEVELOPING,
        OpportunityStage.ARMED,
        OpportunityStage.CMP,
    }
)
_TERMINAL_STAGES = frozenset(
    {
        OpportunityStage.MISSED,
        OpportunityStage.EXPIRED,
        OpportunityStage.INVALIDATED,
    }
)


@dataclass(frozen=True, slots=True)
class OpportunityTransitionAudit:
    """Read-only validation of a lifecycle transition."""

    previous_stage: OpportunityStage | None
    current_stage: OpportunityStage
    disposition: TransitionDisposition
    reason: TransitionReason

    @property
    def legal(self) -> bool:
        return self.disposition is not TransitionDisposition.ILLEGAL


def audit_opportunity_transition(
    previous_stage: OpportunityStage | None,
    current_stage: OpportunityStage,
) -> OpportunityTransitionAudit:
    """Validate a diagnostic lifecycle transition without mutating state."""

    if previous_stage is None:
        disposition = TransitionDisposition.INITIAL
        reason = TransitionReason.NO_PREVIOUS_STAGE
    elif previous_stage is current_stage:
        disposition = TransitionDisposition.LEGAL
        reason = (
            TransitionReason.TERMINAL_STATE_RETAINED
            if previous_stage in _TERMINAL_STAGES
            else TransitionReason.SAME_STAGE
        )
    elif previous_stage in _ACTIVE_STAGES:
        disposition = TransitionDisposition.LEGAL
        reason = (
            TransitionReason.ACTIVE_TO_TERMINAL
            if current_stage in _TERMINAL_STAGES
            else TransitionReason.ACTIVE_STAGE_MOVEMENT
        )
    elif current_stage in _ACTIVE_STAGES:
        disposition = TransitionDisposition.ILLEGAL
        reason = TransitionReason.TERMINAL_REACTIVATION_BLOCKED
    elif previous_stage is OpportunityStage.INVALIDATED:
        disposition = TransitionDisposition.ILLEGAL
        reason = TransitionReason.INVALIDATED_STATE_CHANGED
    else:
        disposition = TransitionDisposition.LEGAL
        reason = TransitionReason.TERMINAL_PRECEDENCE_ADVANCED

    return OpportunityTransitionAudit(
        previous_stage=previous_stage,
        current_stage=current_stage,
        disposition=disposition,
        reason=reason,
    )


@dataclass(frozen=True, slots=True)
class OpportunityCompositionPolicy:
    """Policies used by the read-only Batch 8 composition audit."""

    collision: CollisionResolutionPolicy
    sequence: OpportunitySequencePolicy
    lifecycle: OpportunityLifecyclePolicy


@dataclass(frozen=True, slots=True)
class OpportunityCompositionAudit:
    """Combined diagnostics for two ordered candidate opportunities."""

    collision: OpportunityCollisionAudit
    resolution: CollisionResolutionAudit
    sequence: OpportunitySequenceAudit
    current_lifecycle: OpportunityLifecycleAudit
    follow_up_lifecycle: OpportunityLifecycleAudit
    current_transition: OpportunityTransitionAudit
    follow_up_transition: OpportunityTransitionAudit

    @property
    def transitions_legal(self) -> bool:
        return self.current_transition.legal and self.follow_up_transition.legal


def audit_opportunity_composition(
    current: TradeCandidate,
    follow_up: TradeCandidate,
    *,
    current_observation: OpportunityLifecycleObservation,
    follow_up_observation: OpportunityLifecycleObservation,
    policy: OpportunityCompositionPolicy,
    current_previous_stage: OpportunityStage | None = None,
    follow_up_previous_stage: OpportunityStage | None = None,
) -> OpportunityCompositionAudit:
    """Compose existing diagnostics without filtering, ranking, or mutation."""

    collision = audit_cmp_collision(current, follow_up)
    resolution = audit_collision_resolution(
        current,
        follow_up,
        policy=policy.collision,
    )
    sequence = audit_opportunity_sequence(
        current,
        follow_up,
        policy=policy.sequence,
    )
    current_lifecycle = audit_opportunity_lifecycle(
        current,
        current_observation,
        policy=policy.lifecycle,
        previous_stage=current_previous_stage,
    )
    follow_up_lifecycle = audit_opportunity_lifecycle(
        follow_up,
        follow_up_observation,
        policy=policy.lifecycle,
        previous_stage=follow_up_previous_stage,
    )

    return OpportunityCompositionAudit(
        collision=collision,
        resolution=resolution,
        sequence=sequence,
        current_lifecycle=current_lifecycle,
        follow_up_lifecycle=follow_up_lifecycle,
        current_transition=audit_opportunity_transition(
            current_previous_stage,
            current_lifecycle.stage,
        ),
        follow_up_transition=audit_opportunity_transition(
            follow_up_previous_stage,
            follow_up_lifecycle.stage,
        ),
    )


__all__ = [
    "OpportunityCompositionAudit",
    "OpportunityCompositionPolicy",
    "OpportunityTransitionAudit",
    "TransitionDisposition",
    "TransitionReason",
    "audit_opportunity_composition",
    "audit_opportunity_transition",
]
