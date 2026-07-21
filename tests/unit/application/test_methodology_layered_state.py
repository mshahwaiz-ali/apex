from __future__ import annotations

from apex.application.methodology_layered_state import (
    ExecutionStateInput,
    RiskConditionInput,
    SetupStateInput,
    StructuralBiasInput,
    build_layered_state_snapshot,
    classify_context_state,
    classify_execution_state,
    classify_risk_condition,
    classify_setup_state,
    classify_structural_bias,
)
from apex.application.methodology_strategy_contracts import PrimaryMarketState
from apex.domain.methodology_contracts import (
    ContextState,
    ExecutionState,
    RiskCondition,
    SetupState,
    StructuralBias,
)


def test_execution_classifier_keeps_local_chaos_independent() -> None:
    assert (
        classify_execution_state(
            ExecutionStateInput(
                directional_expansion=True,
                local_chaos=True,
            )
        )
        is ExecutionState.CHAOTIC
    )


def test_execution_classifier_allows_clean_local_state_inside_mixed_context() -> None:
    assert classify_execution_state(ExecutionStateInput()) is ExecutionState.CLEAN


def test_setup_classifier_preserves_failed_breakout_over_broad_breakout() -> None:
    assert (
        classify_setup_state(
            SetupStateInput(
                breakout_attempt=True,
                failed_breakout=True,
            )
        )
        is SetupState.FAILED_BREAKOUT
    )


def test_setup_classifier_preserves_breakout_retest() -> None:
    assert (
        classify_setup_state(
            SetupStateInput(
                confirmed_breakout=True,
                breakout_retest=True,
            )
        )
        is SetupState.BREAKOUT_RETEST
    )


def test_existing_primary_state_maps_to_context_only() -> None:
    assert (
        classify_context_state(PrimaryMarketState.PULLBACK_IN_UPTREND) is ContextState.TRENDING_UP
    )
    assert classify_context_state(PrimaryMarketState.BREAKDOWN_ATTEMPT) is ContextState.EXPANDING


def test_structural_bias_can_be_mixed_near_opposing_authority() -> None:
    assert (
        classify_structural_bias(
            StructuralBiasInput(
                bullish_structure=True,
                major_resistance_nearby=True,
            )
        )
        is StructuralBias.MIXED
    )


def test_risk_condition_is_independent_from_context() -> None:
    assert (
        classify_risk_condition(RiskConditionInput(execution_chaos=True))
        is RiskCondition.EXECUTION_CHAOS
    )
    assert classify_risk_condition(RiskConditionInput(stale_data=True)) is RiskCondition.STALE_DATA


def test_realistic_contradictory_layers_can_coexist() -> None:
    snapshot = build_layered_state_snapshot(
        execution=ExecutionStateInput(rejection=True),
        setup=SetupStateInput(reversal_attempt=True),
        context=PrimaryMarketState.TRENDING_UP,
        structural_bias=StructuralBiasInput(bullish_structure=True),
        risk=RiskConditionInput(),
    )

    assert snapshot.execution_state is ExecutionState.REVERSAL_TRANSITION
    assert snapshot.setup_state is SetupState.REVERSAL_ATTEMPT
    assert snapshot.context_state is ContextState.TRENDING_UP
    assert snapshot.structural_bias is StructuralBias.BULLISH
    assert snapshot.risk_condition is RiskCondition.NORMAL


def test_local_chaos_can_coexist_with_clean_higher_timeframe_bias() -> None:
    snapshot = build_layered_state_snapshot(
        execution=ExecutionStateInput(local_chaos=True),
        setup=SetupStateInput(trend_pullback=True),
        context=PrimaryMarketState.TRENDING_UP,
        structural_bias=StructuralBiasInput(bullish_structure=True),
        risk=RiskConditionInput(execution_chaos=True),
    )

    assert snapshot.execution_state is ExecutionState.CHAOTIC
    assert snapshot.setup_state is SetupState.PULLBACK
    assert snapshot.context_state is ContextState.TRENDING_UP
    assert snapshot.structural_bias is StructuralBias.BULLISH
    assert snapshot.risk_condition is RiskCondition.EXECUTION_CHAOS
