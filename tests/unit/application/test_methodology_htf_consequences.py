from __future__ import annotations

from apex.application.methodology_htf_consequences import (
    HtfConsequencePolicy,
    apply_htf_consequences,
    htf_consequence_payload,
)
from apex.application.methodology_htf_relationship import (
    HtfRelationshipInput,
    classify_htf_relationship,
)
from apex.application.methodology_opportunity_context import (
    HoldingHorizon,
    OpportunityLane,
)
from apex.domain.methodology_contracts import StructuralBias
from apex.strategies.contracts import TradeDirection


def test_countertrend_scalp_gets_closer_target_and_no_runner() -> None:
    assessment = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=TradeDirection.SHORT,
            structural_bias=StructuralBias.BULLISH,
            confirmed_continuation=True,
        )
    )

    result = apply_htf_consequences(
        assessment,
        lane=OpportunityLane.CMP_SCALP,
        holding_horizon=HoldingHorizon.SHORT,
    )

    assert result.allowed is True
    assert result.runner_allowed is False
    assert result.confirmation_required is True
    assert result.target_ceiling_r_multiple == 1.5
    assert result.holding_horizon is HoldingHorizon.SCALP
    assert result.exit_condition_required is True


def test_countertrend_runner_lane_is_not_allowed() -> None:
    assessment = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=TradeDirection.SHORT,
            structural_bias=StructuralBias.BULLISH,
            confirmed_continuation=True,
        )
    )

    result = apply_htf_consequences(
        assessment,
        lane=OpportunityLane.RUNNER,
        holding_horizon=HoldingHorizon.RUNNER,
    )

    assert result.allowed is False
    assert result.runner_allowed is False
    assert result.target_ceiling_r_multiple is None


def test_direct_opposition_rejects_even_scalp_lane() -> None:
    assessment = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=TradeDirection.SHORT,
            structural_bias=StructuralBias.BULLISH,
            nearby_opposing_structure=True,
        )
    )

    result = apply_htf_consequences(
        assessment,
        lane=OpportunityLane.CMP_SCALP,
        holding_horizon=HoldingHorizon.SCALP,
    )

    assert result.allowed is False
    assert result.runner_allowed is False
    assert result.exit_condition_required is True


def test_mild_conflict_penalizes_without_forcing_confirmation() -> None:
    assessment = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=TradeDirection.SHORT,
            structural_bias=StructuralBias.BULLISH,
        )
    )

    result = apply_htf_consequences(
        assessment,
        lane=OpportunityLane.NEARBY_STRUCTURED,
        holding_horizon=HoldingHorizon.SHORT,
    )

    assert result.allowed is True
    assert result.confirmation_required is False
    assert result.runner_allowed is False
    assert result.target_ceiling_r_multiple == 2.5


def test_reversal_attempt_requires_confirmation_and_no_runner() -> None:
    assessment = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=TradeDirection.LONG,
            structural_bias=StructuralBias.BEARISH,
            reversal_attempt=True,
        )
    )

    result = apply_htf_consequences(
        assessment,
        lane=OpportunityLane.NEARBY_STRUCTURED,
        holding_horizon=HoldingHorizon.SHORT,
    )

    assert result.allowed is True
    assert result.confirmation_required is True
    assert result.runner_allowed is False
    assert result.target_ceiling_r_multiple == 2.0


def test_aligned_setup_preserves_runner_authority() -> None:
    assessment = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=TradeDirection.LONG,
            structural_bias=StructuralBias.BULLISH,
        )
    )

    result = apply_htf_consequences(
        assessment,
        lane=OpportunityLane.RUNNER,
        holding_horizon=HoldingHorizon.RUNNER,
    )

    assert result.allowed is True
    assert result.runner_allowed is True
    assert result.target_ceiling_r_multiple is None
    assert result.exit_condition_required is False


def test_payload_is_explicit() -> None:
    assessment = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=TradeDirection.SHORT,
            structural_bias=StructuralBias.BULLISH,
            confirmed_continuation=True,
        )
    )
    result = apply_htf_consequences(
        assessment,
        lane=OpportunityLane.CMP_SCALP,
        holding_horizon=HoldingHorizon.SCALP,
    )

    payload = htf_consequence_payload(result)

    assert payload["allowed"] is True
    assert payload["runner_allowed"] is False
    assert payload["target_ceiling_r_multiple"] == 1.5
    assert payload["holding_horizon"] == "scalp"


def test_custom_policy_controls_live_target_ceilings() -> None:
    assessment = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=TradeDirection.SHORT,
            structural_bias=StructuralBias.BULLISH,
        )
    )
    policy = HtfConsequencePolicy(
        countertrend_scalp_target_ceiling_r=1.25,
        reversal_attempt_target_ceiling_r=1.75,
        mixed_mild_target_ceiling_r=3.1,
        mixed_constrained_target_ceiling_r=1.9,
    )

    result = apply_htf_consequences(
        assessment,
        lane=OpportunityLane.NEARBY_STRUCTURED,
        holding_horizon=HoldingHorizon.SHORT,
        policy=policy,
    )

    assert result.target_ceiling_r_multiple == 3.1
