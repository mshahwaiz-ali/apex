"""Candidate-specific multi-layer methodology state classification."""

from __future__ import annotations

from dataclasses import dataclass

from apex.application.methodology_strategy_contracts import PrimaryMarketState
from apex.domain.methodology_contracts import (
    ContextState,
    ExecutionState,
    LayeredStateSnapshot,
    RiskCondition,
    SetupState,
    StructuralBias,
)


@dataclass(frozen=True, slots=True)
class ExecutionStateInput:
    directional_expansion: bool = False
    micro_pullback: bool = False
    micro_reclaim: bool = False
    rejection: bool = False
    failed_micro_breakout: bool = False
    compression: bool = False
    local_chop: bool = False
    local_chaos: bool = False
    exhaustion: bool = False


@dataclass(frozen=True, slots=True)
class SetupStateInput:
    breakout_attempt: bool = False
    confirmed_breakout: bool = False
    breakout_retest: bool = False
    first_pullback: bool = False
    trend_pullback: bool = False
    range_edge_rejection: bool = False
    failed_breakout: bool = False
    failed_breakdown: bool = False
    reversal_attempt: bool = False
    reversal_confirmed: bool = False
    compression: bool = False
    expansion: bool = False


@dataclass(frozen=True, slots=True)
class StructuralBiasInput:
    bullish_structure: bool = False
    bearish_structure: bool = False
    major_support_nearby: bool = False
    major_resistance_nearby: bool = False


@dataclass(frozen=True, slots=True)
class RiskConditionInput:
    stale_data: bool = False
    thin_liquidity: bool = False
    wide_spread: bool = False
    volatility_shock: bool = False
    execution_chaos: bool = False
    extended: bool = False


def classify_execution_state(value: ExecutionStateInput) -> ExecutionState:
    if value.local_chaos:
        return ExecutionState.CHAOTIC
    if value.directional_expansion:
        return ExecutionState.EXPANDING
    if value.failed_micro_breakout or value.rejection or value.exhaustion:
        return ExecutionState.REVERSAL_TRANSITION
    if value.local_chop:
        return ExecutionState.CHOPPY
    if value.compression or value.micro_pullback or value.micro_reclaim:
        return ExecutionState.MIXED
    return ExecutionState.CLEAN


def classify_setup_state(value: SetupStateInput) -> SetupState:
    if value.reversal_confirmed:
        return SetupState.REVERSAL_CONFIRMED
    if value.failed_breakout:
        return SetupState.FAILED_BREAKOUT
    if value.failed_breakdown:
        return SetupState.FAILED_BREAKDOWN
    if value.breakout_retest:
        return SetupState.BREAKOUT_RETEST
    if value.confirmed_breakout or value.breakout_attempt:
        return SetupState.BREAKOUT
    if value.first_pullback or value.trend_pullback:
        return SetupState.PULLBACK
    if value.range_edge_rejection:
        return SetupState.RANGE
    if value.reversal_attempt:
        return SetupState.REVERSAL_ATTEMPT
    if value.expansion:
        return SetupState.EXPANSION
    if value.compression:
        return SetupState.COMPRESSION
    return SetupState.UNAVAILABLE


def classify_context_state(primary: PrimaryMarketState | None) -> ContextState:
    mapping = {
        PrimaryMarketState.TRENDING_UP: ContextState.TRENDING_UP,
        PrimaryMarketState.PULLBACK_IN_UPTREND: ContextState.TRENDING_UP,
        PrimaryMarketState.POST_BREAKOUT: ContextState.TRENDING_UP,
        PrimaryMarketState.TRENDING_DOWN: ContextState.TRENDING_DOWN,
        PrimaryMarketState.RALLY_IN_DOWNTREND: ContextState.TRENDING_DOWN,
        PrimaryMarketState.POST_BREAKDOWN: ContextState.TRENDING_DOWN,
        PrimaryMarketState.RANGING: ContextState.RANGE_BOUND,
        PrimaryMarketState.COMPRESSING: ContextState.COMPRESSED,
        PrimaryMarketState.BREAKOUT_ATTEMPT: ContextState.EXPANDING,
        PrimaryMarketState.BREAKDOWN_ATTEMPT: ContextState.EXPANDING,
        PrimaryMarketState.EXHAUSTED_UP: ContextState.EXHAUSTED_UP,
        PrimaryMarketState.EXHAUSTED_DOWN: ContextState.EXHAUSTED_DOWN,
        PrimaryMarketState.TRANSITIONAL: ContextState.TRANSITIONAL,
        PrimaryMarketState.REVERSAL_ATTEMPT_UP: ContextState.TRANSITIONAL,
        PrimaryMarketState.REVERSAL_ATTEMPT_DOWN: ContextState.TRANSITIONAL,
        PrimaryMarketState.CHAOTIC: ContextState.MIXED,
    }
    if primary is None:
        return ContextState.UNAVAILABLE
    return mapping[primary]


def classify_structural_bias(value: StructuralBiasInput) -> StructuralBias:
    if value.bullish_structure and value.bearish_structure:
        return StructuralBias.MIXED
    if value.bullish_structure:
        return StructuralBias.MIXED if value.major_resistance_nearby else StructuralBias.BULLISH
    if value.bearish_structure:
        return StructuralBias.MIXED if value.major_support_nearby else StructuralBias.BEARISH
    if value.major_support_nearby and value.major_resistance_nearby:
        return StructuralBias.MIXED
    if value.major_support_nearby or value.major_resistance_nearby:
        return StructuralBias.NEUTRAL
    return StructuralBias.UNAVAILABLE


def classify_risk_condition(value: RiskConditionInput) -> RiskCondition:
    if value.stale_data:
        return RiskCondition.STALE_DATA
    if value.execution_chaos:
        return RiskCondition.EXECUTION_CHAOS
    if value.thin_liquidity:
        return RiskCondition.THIN_LIQUIDITY
    if value.wide_spread:
        return RiskCondition.WIDE_SPREAD
    if value.volatility_shock:
        return RiskCondition.VOLATILITY_SHOCK
    if value.extended:
        return RiskCondition.ELEVATED
    return RiskCondition.NORMAL


def build_layered_state_snapshot(
    *,
    execution: ExecutionStateInput,
    setup: SetupStateInput,
    context: PrimaryMarketState | None,
    structural_bias: StructuralBiasInput,
    risk: RiskConditionInput,
) -> LayeredStateSnapshot:
    return LayeredStateSnapshot(
        execution_state=classify_execution_state(execution),
        setup_state=classify_setup_state(setup),
        context_state=classify_context_state(context),
        structural_bias=classify_structural_bias(structural_bias),
        risk_condition=classify_risk_condition(risk),
    )


__all__ = [
    "ExecutionStateInput",
    "RiskConditionInput",
    "SetupStateInput",
    "StructuralBiasInput",
    "build_layered_state_snapshot",
    "classify_context_state",
    "classify_execution_state",
    "classify_risk_condition",
    "classify_setup_state",
    "classify_structural_bias",
]
