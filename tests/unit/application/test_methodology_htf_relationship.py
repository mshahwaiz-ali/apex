from __future__ import annotations

from apex.application.methodology_htf_relationship import (
    HtfRelationshipInput,
    classify_htf_relationship,
    htf_relationship_payload,
)
from apex.domain.methodology_contracts import (
    RelationshipSeverity,
    StructuralBias,
    TimeframeRelationship,
)
from apex.strategies.contracts import TradeDirection


def test_weak_opposing_bias_gets_mild_mixed_penalty() -> None:
    result = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=TradeDirection.SHORT,
            structural_bias=StructuralBias.BULLISH,
        )
    )

    assert result.relationship is TimeframeRelationship.MIXED
    assert result.severity is RelationshipSeverity.MILD
    assert result.runner_allowed is False
    assert result.hard_reject is False


def test_confirmed_opposing_continuation_becomes_countertrend_scalp() -> None:
    result = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=TradeDirection.SHORT,
            structural_bias=StructuralBias.BULLISH,
            breakout_or_reclaim_confirmed=True,
            swing_structure_confirmed=True,
        )
    )

    assert result.relationship is TimeframeRelationship.COUNTERTREND_SCALP
    assert result.severity is RelationshipSeverity.STRONG
    assert result.confirmation_required is True
    assert result.target_ceiling_required is True
    assert result.runner_allowed is False


def test_direct_nearby_structure_can_hard_reject() -> None:
    result = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=TradeDirection.SHORT,
            structural_bias=StructuralBias.BULLISH,
            nearby_opposing_structure=True,
        )
    )

    assert result.relationship is TimeframeRelationship.DIRECT_STRUCTURAL_OPPOSITION
    assert result.severity is RelationshipSeverity.CRITICAL
    assert result.hard_reject is True


def test_aligned_setup_remains_runner_eligible() -> None:
    result = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=TradeDirection.LONG,
            structural_bias=StructuralBias.BULLISH,
        )
    )

    assert result.relationship is TimeframeRelationship.WITH_TREND
    assert result.severity is RelationshipSeverity.NONE
    assert result.runner_allowed is True
    assert result.target_ceiling_required is False


def test_reversal_attempt_is_not_confirmed_reversal() -> None:
    result = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=TradeDirection.LONG,
            structural_bias=StructuralBias.BEARISH,
            reversal_attempt=True,
        )
    )

    assert result.relationship is TimeframeRelationship.REVERSAL_ATTEMPT
    assert result.relationship is not (TimeframeRelationship.STRUCTURAL_REVERSAL_CONFIRMED)
    assert result.confirmation_required is True


def test_confirmed_structural_reversal_is_separate() -> None:
    result = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=TradeDirection.LONG,
            structural_bias=StructuralBias.BEARISH,
            structural_reversal_confirmed=True,
        )
    )

    assert result.relationship is TimeframeRelationship.STRUCTURAL_REVERSAL_CONFIRMED
    assert result.runner_allowed is True


def test_mixed_or_unavailable_bias_requires_constraints() -> None:
    result = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=TradeDirection.LONG,
            structural_bias=StructuralBias.MIXED,
        )
    )

    assert result.relationship is TimeframeRelationship.MIXED
    assert result.severity is RelationshipSeverity.MODERATE
    assert result.confirmation_required is True


def test_payload_is_explicit_and_deterministic() -> None:
    result = classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=TradeDirection.SHORT,
            structural_bias=StructuralBias.BULLISH,
            confirmed_continuation=True,
        )
    )

    payload = htf_relationship_payload(result)

    assert payload["relationship"] == "countertrend_scalp"
    assert payload["severity"] == "strong"
    assert payload["runner_allowed"] is False
    assert payload["hard_reject"] is False
