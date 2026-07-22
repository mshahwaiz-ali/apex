"""Lane-aware consequences for higher-timeframe relationships."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.application.methodology_opportunity_context import (
    HoldingHorizon,
    OpportunityLane,
)
from apex.domain.methodology_contracts import (
    RelationshipSeverity,
    TimeframeRelationship,
)
from apex.domain.methodology_htf_relationship import (
    HtfRelationshipAssessment,
)


class HtfExecutionTreatment(StrEnum):
    """Typed execution consequence derived from HTF severity and setup horizon."""

    ALIGNED = "aligned"
    SCORE_PENALTY = "score_penalty"
    CONDITIONAL_CONFIRMATION = "conditional_confirmation"
    PROHIBITED = "prohibited"


@dataclass(frozen=True, slots=True)
class HtfConsequencePolicy:
    countertrend_scalp_target_ceiling_r: float = 1.5
    reversal_attempt_target_ceiling_r: float = 2.0
    mixed_mild_target_ceiling_r: float = 2.5
    mixed_constrained_target_ceiling_r: float = 2.0
    mild_conflict_penalty_points: float = 6.0
    moderate_conflict_penalty_points: float = 12.0
    strong_conflict_penalty_points: float = 18.0

    def __post_init__(self) -> None:
        values = (
            self.countertrend_scalp_target_ceiling_r,
            self.reversal_attempt_target_ceiling_r,
            self.mixed_mild_target_ceiling_r,
            self.mixed_constrained_target_ceiling_r,
        )
        if any(not math.isfinite(value) or value <= 0.0 for value in values):
            raise ValueError("HTF consequence target ceilings must be positive and finite")
        penalties = (
            self.mild_conflict_penalty_points,
            self.moderate_conflict_penalty_points,
            self.strong_conflict_penalty_points,
        )
        if any(not math.isfinite(value) or value < 0.0 for value in penalties):
            raise ValueError("HTF consequence penalties must be finite and non-negative")


DEFAULT_HTF_CONSEQUENCE_POLICY = HtfConsequencePolicy()


@dataclass(frozen=True, slots=True)
class HtfConsequence:
    allowed: bool
    runner_allowed: bool
    confirmation_required: bool
    target_ceiling_r_multiple: float | None
    holding_horizon: HoldingHorizon | None
    exit_condition_required: bool
    reasons: tuple[str, ...]
    execution_treatment: HtfExecutionTreatment = HtfExecutionTreatment.ALIGNED
    severity: RelationshipSeverity = RelationshipSeverity.NONE
    score_penalty_points: float = 0.0

    def __post_init__(self) -> None:
        if not self.reasons:
            raise ValueError("HTF consequence requires reasons")
        if not math.isfinite(self.score_penalty_points) or self.score_penalty_points < 0.0:
            raise ValueError("HTF score penalty must be finite and non-negative")
        if self.target_ceiling_r_multiple is not None and self.target_ceiling_r_multiple <= 0.0:
            raise ValueError("target ceiling must be positive")
        if not self.allowed and self.execution_treatment is not HtfExecutionTreatment.PROHIBITED:
            raise ValueError("disallowed HTF consequence must be prohibited")
        if (
            self.execution_treatment is HtfExecutionTreatment.CONDITIONAL_CONFIRMATION
            and not self.confirmation_required
        ):
            raise ValueError("conditional HTF treatment requires confirmation")


def apply_htf_consequences(
    assessment: HtfRelationshipAssessment,
    *,
    lane: OpportunityLane | None,
    holding_horizon: HoldingHorizon | None,
    policy: HtfConsequencePolicy = DEFAULT_HTF_CONSEQUENCE_POLICY,
) -> HtfConsequence:
    if assessment.hard_reject:
        return HtfConsequence(
            allowed=False,
            execution_treatment=HtfExecutionTreatment.PROHIBITED,
            severity=assessment.severity,
            score_penalty_points=policy.strong_conflict_penalty_points,
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
            execution_treatment=(
                HtfExecutionTreatment.CONDITIONAL_CONFIRMATION
                if scalp_lane
                else HtfExecutionTreatment.PROHIBITED
            ),
            severity=assessment.severity,
            score_penalty_points=policy.strong_conflict_penalty_points,
            runner_allowed=False,
            confirmation_required=True,
            target_ceiling_r_multiple=(
                policy.countertrend_scalp_target_ceiling_r if scalp_lane else None
            ),
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
            execution_treatment=HtfExecutionTreatment.CONDITIONAL_CONFIRMATION,
            severity=assessment.severity,
            score_penalty_points=policy.moderate_conflict_penalty_points,
            runner_allowed=False,
            confirmation_required=True,
            target_ceiling_r_multiple=policy.reversal_attempt_target_ceiling_r,
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
            execution_treatment=(
                HtfExecutionTreatment.SCORE_PENALTY
                if mild
                else HtfExecutionTreatment.CONDITIONAL_CONFIRMATION
            ),
            severity=assessment.severity,
            score_penalty_points=(
                policy.mild_conflict_penalty_points
                if mild
                else policy.moderate_conflict_penalty_points
            ),
            runner_allowed=False,
            confirmation_required=not mild,
            target_ceiling_r_multiple=(
                policy.mixed_mild_target_ceiling_r
                if mild
                else policy.mixed_constrained_target_ceiling_r
            ),
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
            execution_treatment=HtfExecutionTreatment.ALIGNED,
            severity=assessment.severity,
            score_penalty_points=0.0,
            runner_allowed=True,
            confirmation_required=False,
            target_ceiling_r_multiple=None,
            holding_horizon=holding_horizon,
            exit_condition_required=False,
            reasons=("confirmed structural reversal restores normal target and runner authority",),
        )

    return HtfConsequence(
        allowed=True,
        execution_treatment=HtfExecutionTreatment.ALIGNED,
        severity=assessment.severity,
        score_penalty_points=0.0,
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
        "execution_treatment": consequence.execution_treatment.value,
        "severity": consequence.severity.value,
        "score_penalty_points": consequence.score_penalty_points,
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
    "DEFAULT_HTF_CONSEQUENCE_POLICY",
    "HtfConsequence",
    "HtfConsequencePolicy",
    "HtfExecutionTreatment",
    "apply_htf_consequences",
    "htf_consequence_payload",
]
