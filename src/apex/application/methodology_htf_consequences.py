"""Lane-aware consequences for higher-timeframe relationships."""

from __future__ import annotations

from dataclasses import dataclass

from apex.application.methodology_htf_relationship import (
    HtfRelationshipAssessment,
)
from apex.application.methodology_opportunity_context import (
    HoldingHorizon,
    OpportunityLane,
)
from apex.domain.methodology_contracts import (
    RelationshipSeverity,
    TimeframeRelationship,
)


@dataclass(frozen=True, slots=True)
class HtfConsequence:
    allowed: bool
    runner_allowed: bool
    confirmation_required: bool
    target_ceiling_r_multiple: float | None
    holding_horizon: HoldingHorizon | None
    exit_condition_required: bool
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.reasons:
            raise ValueError("HTF consequence requires reasons")
        if self.target_ceiling_r_multiple is not None and self.target_ceiling_r_multiple <= 0.0:
            raise ValueError("target ceiling must be positive")


def apply_htf_consequences(
    assessment: HtfRelationshipAssessment,
    *,
    lane: OpportunityLane | None,
    holding_horizon: HoldingHorizon | None,
) -> HtfConsequence:
    if assessment.hard_reject:
        return HtfConsequence(
            allowed=False,
            runner_allowed=False,
            confirmation_required=True,
            target_ceiling_r_multiple=None,
            holding_horizon=holding_horizon,
            exit_condition_required=True,
            reasons=assessment.reasons,
        )

    if assessment.relationship is TimeframeRelationship.COUNTERTREND_SCALP:
        scalp_lane = lane is not None and lane.is_scalp
        return HtfConsequence(
            allowed=scalp_lane,
            runner_allowed=False,
            confirmation_required=True,
            target_ceiling_r_multiple=1.5 if scalp_lane else None,
            holding_horizon=(HoldingHorizon.SCALP if scalp_lane else holding_horizon),
            exit_condition_required=True,
            reasons=(
                "countertrend continuation conflict requires scalp lane, "
                "closer targets, and explicit opposing-structure exit",
            ),
        )

    if assessment.relationship is TimeframeRelationship.REVERSAL_ATTEMPT:
        return HtfConsequence(
            allowed=True,
            runner_allowed=False,
            confirmation_required=True,
            target_ceiling_r_multiple=2.0,
            holding_horizon=holding_horizon,
            exit_condition_required=True,
            reasons=(
                "reversal attempt remains provisional until structural confirmation completes",
            ),
        )

    if assessment.relationship is TimeframeRelationship.MIXED:
        mild = assessment.severity is RelationshipSeverity.MILD
        return HtfConsequence(
            allowed=True,
            runner_allowed=False,
            confirmation_required=not mild,
            target_ceiling_r_multiple=2.5 if mild else 2.0,
            holding_horizon=holding_horizon,
            exit_condition_required=True,
            reasons=(
                "mixed higher-timeframe alignment reduces target authority "
                "and disables runner treatment",
            ),
        )

    if assessment.relationship is TimeframeRelationship.STRUCTURAL_REVERSAL_CONFIRMED:
        return HtfConsequence(
            allowed=True,
            runner_allowed=True,
            confirmation_required=False,
            target_ceiling_r_multiple=None,
            holding_horizon=holding_horizon,
            exit_condition_required=False,
            reasons=("confirmed structural reversal restores normal target and runner authority",),
        )

    return HtfConsequence(
        allowed=True,
        runner_allowed=assessment.runner_allowed,
        confirmation_required=assessment.confirmation_required,
        target_ceiling_r_multiple=None,
        holding_horizon=holding_horizon,
        exit_condition_required=False,
        reasons=assessment.reasons,
    )


def htf_consequence_payload(
    consequence: HtfConsequence,
) -> dict[str, object]:
    return {
        "allowed": consequence.allowed,
        "runner_allowed": consequence.runner_allowed,
        "confirmation_required": consequence.confirmation_required,
        "target_ceiling_r_multiple": consequence.target_ceiling_r_multiple,
        "holding_horizon": (
            None if consequence.holding_horizon is None else consequence.holding_horizon.value
        ),
        "exit_condition_required": consequence.exit_condition_required,
        "reasons": list(consequence.reasons),
    }


__all__ = [
    "HtfConsequence",
    "apply_htf_consequences",
    "htf_consequence_payload",
]
