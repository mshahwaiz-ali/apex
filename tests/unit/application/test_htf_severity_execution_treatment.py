from __future__ import annotations

from dataclasses import dataclass

from apex.application.methodology_horizon_contracts import HoldingHorizon
from apex.application.methodology_htf_consequences import (
    HtfExecutionTreatment,
    apply_htf_consequences,
)
from apex.application.opportunity_portfolio import OpportunityLane
from apex.domain.methodology_contracts import StructuralBias
from apex.domain.methodology_htf_relationship import (
    HtfRelationshipInput,
    classify_htf_relationship,
)


@dataclass(frozen=True)
class _Direction:
    value: str


def test_weak_htf_opposition_is_penalty_not_execution_block() -> None:
    assessment = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=_Direction("long"),
            structural_bias=StructuralBias.BEARISH,
        )
    )
    consequence = apply_htf_consequences(
        assessment,
        lane=OpportunityLane.CMP_SCALP,
        holding_horizon=HoldingHorizon.SCALP,
    )
    assert consequence.allowed is True
    assert consequence.execution_treatment is HtfExecutionTreatment.SCORE_PENALTY
    assert consequence.confirmation_required is False
    assert consequence.score_penalty_points > 0.0
    assert consequence.runner_allowed is False


def test_confirmed_countertrend_continuation_is_conditional_for_scalp() -> None:
    assessment = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=_Direction("long"),
            structural_bias=StructuralBias.BEARISH,
            confirmed_continuation=True,
        )
    )
    consequence = apply_htf_consequences(
        assessment,
        lane=OpportunityLane.CONFIRMATION_SCALP,
        holding_horizon=HoldingHorizon.SCALP,
    )
    assert consequence.allowed is True
    assert consequence.execution_treatment is HtfExecutionTreatment.CONDITIONAL_CONFIRMATION
    assert consequence.confirmation_required is True
    assert consequence.runner_allowed is False
    assert consequence.target_ceiling_r_multiple is not None


def test_confirmed_countertrend_continuation_prohibits_non_scalp_lane() -> None:
    assessment = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=_Direction("short"),
            structural_bias=StructuralBias.BULLISH,
            confirmed_continuation=True,
        )
    )
    consequence = apply_htf_consequences(
        assessment,
        lane=OpportunityLane.RUNNER,
        holding_horizon=HoldingHorizon.RUNNER,
    )
    assert consequence.allowed is False
    assert consequence.execution_treatment is HtfExecutionTreatment.PROHIBITED
    assert consequence.runner_allowed is False


def test_nearby_opposing_structure_remains_hard_prohibition() -> None:
    assessment = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=_Direction("long"),
            structural_bias=StructuralBias.BULLISH,
            nearby_opposing_structure=True,
        )
    )
    consequence = apply_htf_consequences(
        assessment,
        lane=OpportunityLane.CMP_SCALP,
        holding_horizon=HoldingHorizon.SCALP,
    )
    assert consequence.allowed is False
    assert consequence.execution_treatment is HtfExecutionTreatment.PROHIBITED


def test_with_trend_runner_retains_full_authority() -> None:
    assessment = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=_Direction("long"),
            structural_bias=StructuralBias.BULLISH,
        )
    )
    consequence = apply_htf_consequences(
        assessment,
        lane=OpportunityLane.RUNNER,
        holding_horizon=HoldingHorizon.RUNNER,
    )
    assert consequence.allowed is True
    assert consequence.execution_treatment is HtfExecutionTreatment.ALIGNED
    assert consequence.score_penalty_points == 0.0
    assert consequence.runner_allowed is True
