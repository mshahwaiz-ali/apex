from __future__ import annotations

from apex.application.methodology_selected_strategy_verdict import (
    SelectedStrategyVerdictState,
    derive_selected_strategy_verdict,
    selected_strategy_verdict_payload,
)
from apex.application.methodology_strategy_enforcement import (
    StrategyEnforcementAction,
    StrategyEnforcementDecision,
)
from apex.strategies.strategy_types import StrategyType


def _decision(
    strategy: StrategyType,
    action: StrategyEnforcementAction,
) -> StrategyEnforcementDecision:
    return StrategyEnforcementDecision(
        strategy=strategy,
        action=action,
        reason_codes=(f"TEST_{action.value.upper()}",),
        reasons=(f"{strategy.value} is {action.value}",),
    )


def test_no_selected_setup_has_explicit_no_setup_verdict() -> None:
    verdict = derive_selected_strategy_verdict(
        selected_strategy=None,
        decisions=(),
    )

    assert verdict.state is SelectedStrategyVerdictState.NO_SETUP
    assert verdict.strategy is None
    assert verdict.reason_codes == ("NO_SELECTED_SETUP",)


def test_selected_strategy_maps_allow_suppress_and_defer() -> None:
    strategy = StrategyType.TREND_PULLBACK

    allowed = derive_selected_strategy_verdict(
        selected_strategy=strategy,
        decisions=(_decision(strategy, StrategyEnforcementAction.ALLOW),),
    )
    suppressed = derive_selected_strategy_verdict(
        selected_strategy=strategy,
        decisions=(_decision(strategy, StrategyEnforcementAction.SUPPRESS),),
    )
    deferred = derive_selected_strategy_verdict(
        selected_strategy=strategy,
        decisions=(_decision(strategy, StrategyEnforcementAction.DEFER),),
    )

    assert allowed.state is SelectedStrategyVerdictState.ALLOWED
    assert suppressed.state is SelectedStrategyVerdictState.SUPPRESSED
    assert deferred.state is SelectedStrategyVerdictState.DEFERRED


def test_missing_selected_strategy_decision_is_unavailable() -> None:
    verdict = derive_selected_strategy_verdict(
        selected_strategy=StrategyType.RANGE_REVERSAL,
        decisions=(
            _decision(
                StrategyType.TREND_PULLBACK,
                StrategyEnforcementAction.ALLOW,
            ),
        ),
    )

    assert verdict.state is SelectedStrategyVerdictState.UNAVAILABLE
    assert verdict.reason_codes == ("SELECTED_STRATEGY_DECISION_UNAVAILABLE",)


def test_selected_strategy_verdict_payload_is_public_safe() -> None:
    strategy = StrategyType.MOMENTUM_BREAKOUT
    verdict = derive_selected_strategy_verdict(
        selected_strategy=strategy,
        decisions=(_decision(strategy, StrategyEnforcementAction.DEFER),),
    )

    assert selected_strategy_verdict_payload(verdict) == {
        "state": "deferred",
        "strategy": strategy.value,
        "reason_codes": ["TEST_DEFER"],
        "reasons": [f"{strategy.value} is defer"],
    }
