from __future__ import annotations

import pytest

from apex.application.methodology_strategy_layer_requirements import (
    StrategyLayerRequirements,
    strategy_layer_registry_payload,
    strategy_layer_requirements,
)
from apex.domain.methodology_contracts import ExecutionState, SetupState
from apex.strategies.strategy_types import StrategyType


def test_every_strategy_has_layer_requirements() -> None:
    assert {strategy_layer_requirements(strategy).strategy for strategy in StrategyType} == set(
        StrategyType
    )


def test_local_chaos_is_prohibited_for_every_strategy() -> None:
    for strategy in StrategyType:
        declaration = strategy_layer_requirements(strategy)
        assert ExecutionState.CHAOTIC in declaration.prohibited_execution_states


def test_momentum_scalp_is_not_bound_to_one_broad_context_state() -> None:
    declaration = strategy_layer_requirements(StrategyType.MOMENTUM_SCALP)

    assert SetupState.BREAKOUT in declaration.setup_states
    assert SetupState.REVERSAL_ATTEMPT in declaration.setup_states
    assert ExecutionState.EXPANDING in declaration.execution_states
    assert ExecutionState.REVERSAL_TRANSITION in declaration.execution_states


def test_breakout_retest_requires_retest_setup_layer() -> None:
    declaration = strategy_layer_requirements(StrategyType.BREAKOUT_RETEST)

    assert declaration.setup_states == (SetupState.BREAKOUT_RETEST,)


def test_registry_payload_is_deterministic() -> None:
    payload = strategy_layer_registry_payload()

    assert tuple(payload) == tuple(strategy.value for strategy in StrategyType)
    assert payload["momentum_scalp"]["prohibited_execution_states"] == ["chaotic"]


def test_invalid_requirement_rejects_overlap() -> None:
    with pytest.raises(
        ValueError,
        match="compatible and prohibited execution states cannot overlap",
    ):
        StrategyLayerRequirements(
            strategy=StrategyType.MOMENTUM_SCALP,
            execution_states=(ExecutionState.CHAOTIC,),
            setup_states=(SetupState.EXPANSION,),
        )
