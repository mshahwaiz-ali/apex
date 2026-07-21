"""Layer-specific methodology requirements for every strategy family."""

from __future__ import annotations

from dataclasses import dataclass

from apex.domain.methodology_contracts import ExecutionState, SetupState
from apex.strategies.strategy_types import StrategyType


@dataclass(frozen=True, slots=True)
class StrategyLayerRequirements:
    strategy: StrategyType
    execution_states: tuple[ExecutionState, ...]
    setup_states: tuple[SetupState, ...]
    prohibited_execution_states: tuple[ExecutionState, ...] = (ExecutionState.CHAOTIC,)

    def __post_init__(self) -> None:
        if not self.execution_states:
            raise ValueError("strategy layer requirements need execution states")
        if not self.setup_states:
            raise ValueError("strategy layer requirements need setup states")
        if set(self.execution_states) & set(self.prohibited_execution_states):
            raise ValueError("compatible and prohibited execution states cannot overlap")
        for values in (
            self.execution_states,
            self.setup_states,
            self.prohibited_execution_states,
        ):
            if len(set(values)) != len(values):
                raise ValueError("strategy layer requirements must be unique")


_DEFAULT_EXECUTION = (
    ExecutionState.CLEAN,
    ExecutionState.MIXED,
    ExecutionState.EXPANDING,
    ExecutionState.REVERSAL_TRANSITION,
)

_STRATEGY_LAYER_REQUIREMENTS: dict[
    StrategyType,
    StrategyLayerRequirements,
] = {
    StrategyType.MOMENTUM_BREAKOUT: StrategyLayerRequirements(
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        execution_states=(
            ExecutionState.CLEAN,
            ExecutionState.EXPANDING,
        ),
        setup_states=(
            SetupState.BREAKOUT,
            SetupState.EXPANSION,
        ),
    ),
    StrategyType.BREAKOUT_CONTINUATION: StrategyLayerRequirements(
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        execution_states=_DEFAULT_EXECUTION,
        setup_states=(
            SetupState.BREAKOUT,
            SetupState.BREAKOUT_RETEST,
            SetupState.TREND_CONTINUATION,
        ),
    ),
    StrategyType.BREAKOUT_RETEST: StrategyLayerRequirements(
        strategy=StrategyType.BREAKOUT_RETEST,
        execution_states=(
            ExecutionState.CLEAN,
            ExecutionState.MIXED,
            ExecutionState.REVERSAL_TRANSITION,
        ),
        setup_states=(SetupState.BREAKOUT_RETEST,),
    ),
    StrategyType.FIRST_PULLBACK_CONTINUATION: StrategyLayerRequirements(
        strategy=StrategyType.FIRST_PULLBACK_CONTINUATION,
        execution_states=_DEFAULT_EXECUTION,
        setup_states=(
            SetupState.PULLBACK,
            SetupState.TREND_CONTINUATION,
        ),
    ),
    StrategyType.TREND_PULLBACK: StrategyLayerRequirements(
        strategy=StrategyType.TREND_PULLBACK,
        execution_states=_DEFAULT_EXECUTION,
        setup_states=(
            SetupState.PULLBACK,
            SetupState.TREND_CONTINUATION,
        ),
    ),
    StrategyType.COMPRESSION_EXPANSION: StrategyLayerRequirements(
        strategy=StrategyType.COMPRESSION_EXPANSION,
        execution_states=(
            ExecutionState.CLEAN,
            ExecutionState.MIXED,
            ExecutionState.EXPANDING,
        ),
        setup_states=(
            SetupState.COMPRESSION,
            SetupState.EXPANSION,
            SetupState.BREAKOUT,
        ),
    ),
    StrategyType.RANGE_REVERSAL: StrategyLayerRequirements(
        strategy=StrategyType.RANGE_REVERSAL,
        execution_states=(
            ExecutionState.CLEAN,
            ExecutionState.MIXED,
            ExecutionState.REVERSAL_TRANSITION,
        ),
        setup_states=(
            SetupState.RANGE,
            SetupState.REVERSAL_ATTEMPT,
        ),
    ),
    StrategyType.FAILED_BREAKOUT_REVERSAL: StrategyLayerRequirements(
        strategy=StrategyType.FAILED_BREAKOUT_REVERSAL,
        execution_states=(
            ExecutionState.CLEAN,
            ExecutionState.MIXED,
            ExecutionState.REVERSAL_TRANSITION,
        ),
        setup_states=(
            SetupState.FAILED_BREAKOUT,
            SetupState.FAILED_BREAKDOWN,
            SetupState.REVERSAL_ATTEMPT,
        ),
    ),
    StrategyType.LIQUIDITY_REJECTION_REVERSAL: StrategyLayerRequirements(
        strategy=StrategyType.LIQUIDITY_REJECTION_REVERSAL,
        execution_states=(
            ExecutionState.CLEAN,
            ExecutionState.MIXED,
            ExecutionState.REVERSAL_TRANSITION,
        ),
        setup_states=(
            SetupState.RANGE,
            SetupState.REVERSAL_ATTEMPT,
            SetupState.REVERSAL_CONFIRMED,
        ),
    ),
    StrategyType.VWAP_RECLAIM_REJECTION: StrategyLayerRequirements(
        strategy=StrategyType.VWAP_RECLAIM_REJECTION,
        execution_states=(
            ExecutionState.CLEAN,
            ExecutionState.MIXED,
            ExecutionState.REVERSAL_TRANSITION,
        ),
        setup_states=(
            SetupState.PULLBACK,
            SetupState.REVERSAL_ATTEMPT,
            SetupState.TREND_CONTINUATION,
        ),
    ),
    StrategyType.MOMENTUM_SCALP: StrategyLayerRequirements(
        strategy=StrategyType.MOMENTUM_SCALP,
        execution_states=(
            ExecutionState.CLEAN,
            ExecutionState.MIXED,
            ExecutionState.EXPANDING,
            ExecutionState.REVERSAL_TRANSITION,
        ),
        setup_states=(
            SetupState.BREAKOUT,
            SetupState.EXPANSION,
            SetupState.TREND_CONTINUATION,
            SetupState.REVERSAL_ATTEMPT,
        ),
    ),
    StrategyType.EXHAUSTION_REVERSAL: StrategyLayerRequirements(
        strategy=StrategyType.EXHAUSTION_REVERSAL,
        execution_states=(
            ExecutionState.CLEAN,
            ExecutionState.MIXED,
            ExecutionState.REVERSAL_TRANSITION,
        ),
        setup_states=(
            SetupState.REVERSAL_ATTEMPT,
            SetupState.REVERSAL_CONFIRMED,
            SetupState.FAILED_BREAKOUT,
            SetupState.FAILED_BREAKDOWN,
        ),
    ),
}


def strategy_layer_requirements(
    strategy: StrategyType,
) -> StrategyLayerRequirements:
    return _STRATEGY_LAYER_REQUIREMENTS[strategy]


def strategy_layer_registry_payload() -> dict[str, dict[str, list[str]]]:
    return {
        strategy.value: {
            "execution_states": [state.value for state in declaration.execution_states],
            "setup_states": [state.value for state in declaration.setup_states],
            "prohibited_execution_states": [
                state.value for state in declaration.prohibited_execution_states
            ],
        }
        for strategy, declaration in _STRATEGY_LAYER_REQUIREMENTS.items()
    }


__all__ = [
    "StrategyLayerRequirements",
    "strategy_layer_registry_payload",
    "strategy_layer_requirements",
]
