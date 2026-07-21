"""Direction-aware higher-timeframe relationship classification."""

from __future__ import annotations

from dataclasses import dataclass

from apex.domain.methodology_contracts import (
    RelationshipSeverity,
    StructuralBias,
    TimeframeRelationship,
)
from apex.strategies.contracts import TradeDirection


@dataclass(frozen=True, slots=True)
class HtfRelationshipInput:
    trade_direction: TradeDirection
    structural_bias: StructuralBias
    confirmed_continuation: bool = False
    breakout_or_reclaim_confirmed: bool = False
    swing_structure_confirmed: bool = False
    participation_confirmed: bool = False
    nearby_opposing_structure: bool = False
    reversal_attempt: bool = False
    structural_reversal_confirmed: bool = False


@dataclass(frozen=True, slots=True)
class HtfRelationshipAssessment:
    relationship: TimeframeRelationship
    severity: RelationshipSeverity
    runner_allowed: bool
    confirmation_required: bool
    target_ceiling_required: bool
    hard_reject: bool
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.reasons:
            raise ValueError("HTF relationship assessment requires reasons")


def _direction_matches_bias(
    direction: TradeDirection,
    bias: StructuralBias,
) -> bool:
    return (direction is TradeDirection.LONG and bias is StructuralBias.BULLISH) or (
        direction is TradeDirection.SHORT and bias is StructuralBias.BEARISH
    )


def _direction_opposes_bias(
    direction: TradeDirection,
    bias: StructuralBias,
) -> bool:
    return (direction is TradeDirection.LONG and bias is StructuralBias.BEARISH) or (
        direction is TradeDirection.SHORT and bias is StructuralBias.BULLISH
    )


def classify_htf_relationship(
    value: HtfRelationshipInput,
) -> HtfRelationshipAssessment:
    if value.nearby_opposing_structure:
        return HtfRelationshipAssessment(
            relationship=TimeframeRelationship.DIRECT_STRUCTURAL_OPPOSITION,
            severity=RelationshipSeverity.CRITICAL,
            runner_allowed=False,
            confirmation_required=True,
            target_ceiling_required=True,
            hard_reject=True,
            reasons=("nearby opposing higher-timeframe structure destroys usable reward space",),
        )

    if value.structural_reversal_confirmed:
        return HtfRelationshipAssessment(
            relationship=TimeframeRelationship.STRUCTURAL_REVERSAL_CONFIRMED,
            severity=RelationshipSeverity.NONE,
            runner_allowed=True,
            confirmation_required=False,
            target_ceiling_required=False,
            hard_reject=False,
            reasons=("higher-timeframe reversal is structurally confirmed in trade direction",),
        )

    if value.reversal_attempt:
        return HtfRelationshipAssessment(
            relationship=TimeframeRelationship.REVERSAL_ATTEMPT,
            severity=RelationshipSeverity.MODERATE,
            runner_allowed=False,
            confirmation_required=True,
            target_ceiling_required=True,
            hard_reject=False,
            reasons=("trade depends on an unconfirmed higher-timeframe reversal attempt",),
        )

    if _direction_matches_bias(
        value.trade_direction,
        value.structural_bias,
    ):
        return HtfRelationshipAssessment(
            relationship=TimeframeRelationship.WITH_TREND,
            severity=RelationshipSeverity.NONE,
            runner_allowed=True,
            confirmation_required=False,
            target_ceiling_required=False,
            hard_reject=False,
            reasons=("trade direction aligns with higher-timeframe structure",),
        )

    if _direction_opposes_bias(
        value.trade_direction,
        value.structural_bias,
    ):
        continuation_evidence = sum(
            (
                value.breakout_or_reclaim_confirmed,
                value.swing_structure_confirmed,
                value.participation_confirmed,
            )
        )
        strong_continuation = value.confirmed_continuation or continuation_evidence >= 2
        if strong_continuation:
            return HtfRelationshipAssessment(
                relationship=TimeframeRelationship.COUNTERTREND_SCALP,
                severity=RelationshipSeverity.STRONG,
                runner_allowed=False,
                confirmation_required=True,
                target_ceiling_required=True,
                hard_reject=False,
                reasons=(
                    "trade opposes confirmed higher-timeframe continuation; "
                    "scalp-only treatment required",
                ),
            )
        return HtfRelationshipAssessment(
            relationship=TimeframeRelationship.MIXED,
            severity=RelationshipSeverity.MILD,
            runner_allowed=False,
            confirmation_required=False,
            target_ceiling_required=True,
            hard_reject=False,
            reasons=(
                "trade direction opposes weak higher-timeframe bias without confirmed continuation",
            ),
        )

    return HtfRelationshipAssessment(
        relationship=TimeframeRelationship.MIXED,
        severity=RelationshipSeverity.MODERATE,
        runner_allowed=False,
        confirmation_required=True,
        target_ceiling_required=True,
        hard_reject=False,
        reasons=("higher-timeframe structure is neutral, mixed, or unavailable",),
    )


def htf_relationship_payload(
    assessment: HtfRelationshipAssessment,
) -> dict[str, object]:
    return {
        "relationship": assessment.relationship.value,
        "severity": assessment.severity.value,
        "runner_allowed": assessment.runner_allowed,
        "confirmation_required": assessment.confirmation_required,
        "target_ceiling_required": assessment.target_ceiling_required,
        "hard_reject": assessment.hard_reject,
        "reasons": list(assessment.reasons),
    }


__all__ = [
    "HtfRelationshipAssessment",
    "HtfRelationshipInput",
    "classify_htf_relationship",
    "htf_relationship_payload",
]
