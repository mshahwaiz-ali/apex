"""Lane and horizon context for methodology decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.application.opportunity_portfolio import (
    ActionabilityState,
    SequenceRole,
    TradeOpportunity,
    build_actionability_state_assessment,
)
from apex.strategies.strategy_types import StrategyType


class OpportunityLane(StrEnum):
    CMP_SCALP = "cmp_scalp"
    CONFIRMATION_SCALP = "confirmation_scalp"
    PULLBACK_SCALP = "pullback_scalp"
    NEARBY_STRUCTURED = "nearby_structured"
    RUNNER = "runner"
    DEVELOPING = "developing"

    @property
    def is_scalp(self) -> bool:
        return self in {
            OpportunityLane.CMP_SCALP,
            OpportunityLane.CONFIRMATION_SCALP,
            OpportunityLane.PULLBACK_SCALP,
        }


class HoldingHorizon(StrEnum):
    SCALP = "scalp"
    SHORT = "short"
    STRUCTURED = "structured"
    RUNNER = "runner"


class HigherTimeframeAuthority(StrEnum):
    WARNING_AND_TARGET_CEILING = "warning_and_target_ceiling"
    CONTEXTUAL_PENALTY = "contextual_penalty"
    STRICT = "strict"


@dataclass(frozen=True, slots=True)
class OpportunityMethodologyContext:
    lane: OpportunityLane
    holding_horizon: HoldingHorizon
    higher_timeframe_authority: HigherTimeframeAuthority


_SCALP_STRATEGIES = {
    StrategyType.MOMENTUM_SCALP,
    StrategyType.VWAP_RECLAIM_REJECTION,
    StrategyType.RANGE_REVERSAL,
    StrategyType.FAILED_BREAKOUT_REVERSAL,
    StrategyType.LIQUIDITY_REJECTION_REVERSAL,
    StrategyType.EXHAUSTION_REVERSAL,
}


def infer_opportunity_methodology_context(
    opportunity: TradeOpportunity,
) -> OpportunityMethodologyContext:
    if opportunity.sequence_role is SequenceRole.RUNNER:
        return OpportunityMethodologyContext(
            lane=OpportunityLane.RUNNER,
            holding_horizon=HoldingHorizon.RUNNER,
            higher_timeframe_authority=HigherTimeframeAuthority.STRICT,
        )

    setup = opportunity.setup
    assessment = build_actionability_state_assessment(
        setup,
        sequence_role=opportunity.sequence_role,
    )

    if opportunity.sequence_role is SequenceRole.FOLLOW_UP:
        return OpportunityMethodologyContext(
            lane=OpportunityLane.DEVELOPING,
            holding_horizon=HoldingHorizon.STRUCTURED,
            higher_timeframe_authority=HigherTimeframeAuthority.CONTEXTUAL_PENALTY,
        )

    if opportunity.sequence_role is SequenceRole.NEARBY:
        lane = (
            OpportunityLane.PULLBACK_SCALP
            if setup.strategy in _SCALP_STRATEGIES
            else OpportunityLane.NEARBY_STRUCTURED
        )
        return OpportunityMethodologyContext(
            lane=lane,
            holding_horizon=HoldingHorizon.SHORT if lane.is_scalp else HoldingHorizon.STRUCTURED,
            higher_timeframe_authority=(
                HigherTimeframeAuthority.WARNING_AND_TARGET_CEILING
                if lane.is_scalp
                else HigherTimeframeAuthority.CONTEXTUAL_PENALTY
            ),
        )

    confirmation_pending = assessment.state in {
        ActionabilityState.EXECUTE_ON_MICRO_CONFIRMATION,
        ActionabilityState.PLACE_LIMIT_WITH_ACTIVATION,
        ActionabilityState.RETEST_PREFERRED,
        ActionabilityState.RECLAIM_REQUIRED,
    }
    lane = OpportunityLane.CONFIRMATION_SCALP if confirmation_pending else OpportunityLane.CMP_SCALP
    return OpportunityMethodologyContext(
        lane=lane,
        holding_horizon=HoldingHorizon.SCALP,
        higher_timeframe_authority=HigherTimeframeAuthority.WARNING_AND_TARGET_CEILING,
    )


__all__ = [
    "HigherTimeframeAuthority",
    "HoldingHorizon",
    "OpportunityLane",
    "OpportunityMethodologyContext",
    "infer_opportunity_methodology_context",
]
