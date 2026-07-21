"""Lane and horizon context for methodology decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.application.opportunity_portfolio import (
    ActionabilityState,
    OpportunityLane,
    SequenceRole,
    TradeOpportunity,
    build_actionability_state_assessment,
)
from apex.strategies.contracts import EntryMode, TradeCandidate
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


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


def infer_candidate_methodology_context(
    candidate: TradeCandidate,
    *,
    entry_status: EntryStatus,
) -> OpportunityMethodologyContext:
    """Infer pre-ranking lane context so broad market state cannot erase scalps."""

    executable = entry_status in {EntryStatus.READY_NOW, EntryStatus.AGGRESSIVE_NOW}
    if executable:
        confirmation_pending = candidate.provisional or candidate.entry.mode in {
            EntryMode.RETEST,
            EntryMode.SWEEP_RECOVERY,
            EntryMode.MOMENTUM_CONTINUATION,
        }
        lane = (
            OpportunityLane.CONFIRMATION_SCALP
            if confirmation_pending
            else OpportunityLane.CMP_SCALP
        )
        return OpportunityMethodologyContext(
            lane=lane,
            holding_horizon=HoldingHorizon.SCALP,
            higher_timeframe_authority=HigherTimeframeAuthority.WARNING_AND_TARGET_CEILING,
        )

    pullback = candidate.entry.mode in {EntryMode.PULLBACK, EntryMode.SCALED_ENTRY}
    lane = (
        OpportunityLane.PULLBACK_SCALP
        if pullback or candidate.strategy in _SCALP_STRATEGIES
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
    if opportunity.lane is not None:
        lane = opportunity.effective_lane
        if lane is OpportunityLane.RUNNER:
            return OpportunityMethodologyContext(
                lane=lane,
                holding_horizon=HoldingHorizon.RUNNER,
                higher_timeframe_authority=HigherTimeframeAuthority.STRICT,
            )
        if lane is OpportunityLane.DEVELOPING:
            return OpportunityMethodologyContext(
                lane=lane,
                holding_horizon=HoldingHorizon.STRUCTURED,
                higher_timeframe_authority=HigherTimeframeAuthority.CONTEXTUAL_PENALTY,
            )
        return OpportunityMethodologyContext(
            lane=lane,
            holding_horizon=(
                HoldingHorizon.SHORT
                if lane
                in {
                    OpportunityLane.PULLBACK_SCALP,
                    OpportunityLane.NEARBY_STRUCTURED,
                }
                else HoldingHorizon.SCALP
                if lane.is_scalp
                else HoldingHorizon.STRUCTURED
            ),
            higher_timeframe_authority=(
                HigherTimeframeAuthority.WARNING_AND_TARGET_CEILING
                if lane.is_scalp
                else HigherTimeframeAuthority.CONTEXTUAL_PENALTY
            ),
        )
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
        lane = opportunity.effective_lane
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
    "infer_candidate_methodology_context",
    "infer_opportunity_methodology_context",
]
