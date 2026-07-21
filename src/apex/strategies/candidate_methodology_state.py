"""Derive conservative layered methodology state for strategy candidates."""

from __future__ import annotations

from dataclasses import replace

from apex.domain.methodology_contracts import (
    ContextState,
    ContinuationState,
    ExecutionState,
    LayeredStateSnapshot,
    RiskCondition,
    SetupState,
    StructuralBias,
)
from apex.domain.methodology_htf_relationship import (
    HtfRelationshipAssessment,
    HtfRelationshipInput,
    classify_htf_relationship,
)
from apex.strategies.context import StrategyContext, TimeframeContext, TimeframeRole
from apex.strategies.contracts import TradeCandidate
from apex.strategies.strategy_types import StrategyType
from apex.structure.contracts import (
    BreakDirection,
    BreakQuality,
    ConfirmationStatus,
    TrendDirection,
)
from apex.structure.regime import MarketRegime, classify_market_regime

_DEFAULT_LAYERED_STATE = LayeredStateSnapshot()

_HIGHER_TIMEFRAME_ROLES = {
    TimeframeRole.LONG_TERM_MACRO,
    TimeframeRole.SWING,
    TimeframeRole.MACRO,
    TimeframeRole.INTERMEDIATE,
}
_BULLISH_TRENDS = {
    TrendDirection.STRONG_BULLISH,
    TrendDirection.BULLISH,
    TrendDirection.WEAK_BULLISH,
}
_BEARISH_TRENDS = {
    TrendDirection.STRONG_BEARISH,
    TrendDirection.BEARISH,
    TrendDirection.WEAK_BEARISH,
}

_REVERSAL_STRATEGIES = {
    StrategyType.RANGE_REVERSAL,
    StrategyType.FAILED_BREAKOUT_REVERSAL,
    StrategyType.LIQUIDITY_REJECTION_REVERSAL,
    StrategyType.VWAP_RECLAIM_REJECTION,
    StrategyType.EXHAUSTION_REVERSAL,
}
_EXPANSION_STRATEGIES = {
    StrategyType.MOMENTUM_BREAKOUT,
    StrategyType.BREAKOUT_CONTINUATION,
    StrategyType.COMPRESSION_EXPANSION,
    StrategyType.MOMENTUM_SCALP,
}

_SETUP_STATE_BY_STRATEGY = {
    StrategyType.MOMENTUM_BREAKOUT: SetupState.BREAKOUT,
    StrategyType.BREAKOUT_CONTINUATION: SetupState.BREAKOUT,
    StrategyType.BREAKOUT_RETEST: SetupState.BREAKOUT_RETEST,
    StrategyType.FIRST_PULLBACK_CONTINUATION: SetupState.PULLBACK,
    StrategyType.TREND_PULLBACK: SetupState.PULLBACK,
    StrategyType.COMPRESSION_EXPANSION: SetupState.COMPRESSION,
    StrategyType.RANGE_REVERSAL: SetupState.RANGE,
    StrategyType.FAILED_BREAKOUT_REVERSAL: SetupState.FAILED_BREAKOUT,
    StrategyType.LIQUIDITY_REJECTION_REVERSAL: SetupState.REVERSAL_ATTEMPT,
    StrategyType.VWAP_RECLAIM_REJECTION: SetupState.REVERSAL_ATTEMPT,
    StrategyType.MOMENTUM_SCALP: SetupState.TREND_CONTINUATION,
    StrategyType.EXHAUSTION_REVERSAL: SetupState.REVERSAL_ATTEMPT,
}

_CONTEXT_STATE_BY_REGIME = {
    MarketRegime.STRONG_UPTREND: ContextState.TRENDING_UP,
    MarketRegime.WEAK_UPTREND: ContextState.TRENDING_UP,
    MarketRegime.STRONG_DOWNTREND: ContextState.TRENDING_DOWN,
    MarketRegime.WEAK_DOWNTREND: ContextState.TRENDING_DOWN,
    MarketRegime.STABLE_RANGE: ContextState.RANGE_BOUND,
    MarketRegime.VOLATILE_RANGE: ContextState.RANGE_BOUND,
    MarketRegime.RANGE: ContextState.RANGE_BOUND,
    MarketRegime.COMPRESSION: ContextState.COMPRESSED,
    MarketRegime.BREAKOUT_EXPANSION: ContextState.EXPANDING,
    MarketRegime.REVERSAL_TRANSITION: ContextState.TRANSITIONAL,
    MarketRegime.HIGH_VOLATILITY_CHAOS: ContextState.MIXED,
    MarketRegime.LOW_VOLATILITY_STAGNATION: ContextState.COMPRESSED,
    MarketRegime.LOW_LIQUIDITY: ContextState.MIXED,
    MarketRegime.UNCERTAIN: ContextState.UNAVAILABLE,
    MarketRegime.STRONG_TREND: ContextState.MIXED,
    MarketRegime.WEAK_TREND: ContextState.MIXED,
}


def attach_candidate_methodology_state(
    *,
    candidate: TradeCandidate,
    context: StrategyContext,
    regime: MarketRegime,
) -> TradeCandidate:
    if candidate.layered_state != _DEFAULT_LAYERED_STATE:
        return candidate

    htf_relationship = _higher_timeframe_relationship(candidate, context)
    snapshot = LayeredStateSnapshot(
        execution_state=_execution_state(candidate, context, regime),
        setup_state=_SETUP_STATE_BY_STRATEGY[candidate.strategy],
        context_state=_CONTEXT_STATE_BY_REGIME[regime],
        structural_bias=_structural_bias(context),
        risk_condition=_risk_condition(candidate, context, regime),
        timeframe_relationship=(
            _DEFAULT_LAYERED_STATE.timeframe_relationship
            if htf_relationship is None
            else htf_relationship.relationship
        ),
        relationship_severity=(
            _DEFAULT_LAYERED_STATE.relationship_severity
            if htf_relationship is None
            else htf_relationship.severity
        ),
        continuation_state=_continuation_state(candidate),
    )
    return replace(candidate, layered_state=snapshot)


def _execution_state(
    candidate: TradeCandidate,
    context: StrategyContext,
    regime: MarketRegime,
) -> ExecutionState:
    frame = context.decision_frame
    if frame.is_stale or regime is MarketRegime.HIGH_VOLATILITY_CHAOS:
        return ExecutionState.CHAOTIC
    if candidate.strategy in _REVERSAL_STRATEGIES:
        return ExecutionState.REVERSAL_TRANSITION
    confirmation_complete = candidate.metadata.get("entry_confirmation_complete") is True
    if candidate.provisional or context.provisional or not confirmation_complete:
        return ExecutionState.MIXED
    if regime in {MarketRegime.STABLE_RANGE, MarketRegime.VOLATILE_RANGE}:
        return ExecutionState.MIXED
    if candidate.strategy in _EXPANSION_STRATEGIES:
        return ExecutionState.EXPANDING
    return ExecutionState.CLEAN


def _higher_timeframe_relationship(
    candidate: TradeCandidate,
    context: StrategyContext,
) -> HtfRelationshipAssessment | None:
    frames = tuple(frame for frame in context.frames if frame.role in _HIGHER_TIMEFRAME_ROLES)
    if not frames:
        return None

    bias = _aggregate_higher_timeframe_bias(frames)
    if bias is StructuralBias.UNAVAILABLE:
        return None

    return classify_htf_relationship(
        HtfRelationshipInput(
            trade_direction=candidate.direction,
            structural_bias=bias,
            confirmed_continuation=_higher_timeframe_continuation_confirmed(
                frames,
                bias=bias,
            ),
        )
    )


def _aggregate_higher_timeframe_bias(
    frames: tuple[TimeframeContext, ...],
) -> StructuralBias:
    directions = tuple(frame.structure.trend.direction for frame in frames)
    bullish = any(direction in _BULLISH_TRENDS for direction in directions)
    bearish = any(direction in _BEARISH_TRENDS for direction in directions)
    if bullish and bearish:
        return StructuralBias.MIXED
    if bullish:
        return StructuralBias.BULLISH
    if bearish:
        return StructuralBias.BEARISH
    if any(direction is TrendDirection.TRANSITION for direction in directions):
        return StructuralBias.MIXED
    if directions and all(direction is TrendDirection.RANGE for direction in directions):
        return StructuralBias.NEUTRAL
    return StructuralBias.UNAVAILABLE


def _higher_timeframe_continuation_confirmed(
    frames: tuple[TimeframeContext, ...],
    *,
    bias: StructuralBias,
) -> bool:
    expected_break = (
        BreakDirection.BULLISH
        if bias is StructuralBias.BULLISH
        else BreakDirection.BEARISH
        if bias is StructuralBias.BEARISH
        else None
    )
    if expected_break is None:
        return False

    expected_trends = _BULLISH_TRENDS if bias is StructuralBias.BULLISH else _BEARISH_TRENDS
    return any(
        frame.structure.trend.direction in expected_trends
        and (
            classify_market_regime(frame.structure) is MarketRegime.BREAKOUT_EXPANSION
            or any(
                event.direction is expected_break
                and event.confirmation is ConfirmationStatus.CONFIRMED
                and event.quality in {BreakQuality.VALID, BreakQuality.STRONG}
                for event in frame.structure.breaks
            )
        )
        for frame in frames
    )


def _structural_bias(context: StrategyContext) -> StructuralBias:
    direction = context.decision_frame.structure.trend.direction
    if direction in {
        TrendDirection.STRONG_BULLISH,
        TrendDirection.BULLISH,
        TrendDirection.WEAK_BULLISH,
    }:
        return StructuralBias.BULLISH
    if direction in {
        TrendDirection.STRONG_BEARISH,
        TrendDirection.BEARISH,
        TrendDirection.WEAK_BEARISH,
    }:
        return StructuralBias.BEARISH
    if direction is TrendDirection.RANGE:
        return StructuralBias.NEUTRAL
    if direction is TrendDirection.TRANSITION:
        return StructuralBias.MIXED
    return StructuralBias.UNAVAILABLE


def _risk_condition(
    candidate: TradeCandidate,
    context: StrategyContext,
    regime: MarketRegime,
) -> RiskCondition:
    frame = context.decision_frame
    if frame.is_stale:
        return RiskCondition.STALE_DATA
    if regime is MarketRegime.HIGH_VOLATILITY_CHAOS:
        return RiskCondition.EXECUTION_CHAOS
    if regime is MarketRegime.LOW_LIQUIDITY:
        return RiskCondition.THIN_LIQUIDITY
    spreads = tuple(
        value
        for value in (
            frame.spread_percentage,
            frame.order_book_spread_percentage,
        )
        if value is not None
    )
    if spreads and max(spreads) >= 0.25:
        return RiskCondition.WIDE_SPREAD
    if candidate.entry.is_extended or frame.data_confidence < 0.75:
        return RiskCondition.ELEVATED
    return RiskCondition.NORMAL


def _continuation_state(candidate: TradeCandidate) -> ContinuationState:
    raw = candidate.metadata.get("continuation_state")
    explicit = {
        "fresh_break": ContinuationState.FRESH_CONTINUATION,
        "first_continuation": ContinuationState.FRESH_CONTINUATION,
        "mature_continuation": ContinuationState.MATURE_CONTINUATION,
        "exhausted": ContinuationState.EXHAUSTION_WARNING,
    }
    if isinstance(raw, str) and raw in explicit:
        return explicit[raw]
    if candidate.strategy is StrategyType.FAILED_BREAKOUT_REVERSAL:
        return ContinuationState.FAILED_BREAKOUT
    if candidate.strategy in {
        StrategyType.LIQUIDITY_REJECTION_REVERSAL,
        StrategyType.VWAP_RECLAIM_REJECTION,
        StrategyType.EXHAUSTION_REVERSAL,
        StrategyType.RANGE_REVERSAL,
    }:
        return ContinuationState.REVERSAL_WATCH
    if candidate.entry.is_extended:
        return ContinuationState.LATE_CHASE
    return ContinuationState.UNAVAILABLE


__all__ = ["attach_candidate_methodology_state"]
