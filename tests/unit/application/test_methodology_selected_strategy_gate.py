from __future__ import annotations

from datetime import UTC, datetime

from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoveryAssessment,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    TakeProfit,
)
from apex.application.methodology_selected_strategy_gate import (
    MethodologyGateMode,
    apply_selected_strategy_gate,
)
from apex.application.methodology_selected_strategy_verdict import (
    SelectedStrategyVerdict,
    SelectedStrategyVerdictState,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


def _assessment() -> DiscoveryAssessment:
    setup = DiscoverySetup(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.TREND_PULLBACK,
        entry_status=EntryStatus.READY_NOW,
        decision_time=datetime(2026, 7, 18, tzinfo=UTC),
        candidate_id="candidate-1",
        confidence_score=70.0,
        entry=ActionableEntry(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=100.0,
            maximum_chase_price=102.0,
            current_price_inside_zone=True,
        ),
        stop_loss=StopLoss(
            price=97.0,
            distance=3.0,
            distance_pct=3.0,
            rationale=("below pullback structure",),
        ),
        take_profits=(
            TakeProfit(
                label="TP1",
                price=106.0,
                reward=6.0,
                risk_reward=2.0,
                rationale=("next structural resistance",),
            ),
        ),
        management_policies=(
            ManagementPolicy(
                kind=ManagementPolicyType.TIME_EXIT,
                trigger="setup expiry",
                action="close remaining position",
                rationale=("avoid stale exposure",),
            ),
        ),
    )
    return DiscoveryAssessment(
        symbol="BTCUSDT",
        decision_time=setup.decision_time,
        setup=setup,
    )


def _verdict(state: SelectedStrategyVerdictState) -> SelectedStrategyVerdict:
    return SelectedStrategyVerdict(
        state=state,
        strategy=StrategyType.TREND_PULLBACK,
        reason_codes=(f"TEST_{state.value.upper()}",),
        reasons=(f"trend pullback is {state.value}",),
    )


def test_shadow_mode_never_changes_selected_setup() -> None:
    assessment = _assessment()

    result = apply_selected_strategy_gate(
        assessment,
        _verdict(SelectedStrategyVerdictState.SUPPRESSED),
    )

    assert result.mode is MethodologyGateMode.SHADOW
    assert result.changed is False
    assert result.assessment is assessment
    assert result.assessment.setup is not None


def test_enforce_mode_suppresses_only_explicit_conflict() -> None:
    result = apply_selected_strategy_gate(
        _assessment(),
        _verdict(SelectedStrategyVerdictState.SUPPRESSED),
        mode=MethodologyGateMode.ENFORCE,
    )

    assert result.changed is True
    assert result.assessment.setup is None
    assert result.assessment.reasons == ("trend pullback is suppressed",)
    assert result.reason_codes == ("METHODOLOGY_SELECTED_STRATEGY_SUPPRESSED",)


def test_enforce_mode_allows_allowed_and_deferred_verdicts() -> None:
    for state in (
        SelectedStrategyVerdictState.ALLOWED,
        SelectedStrategyVerdictState.DEFERRED,
        SelectedStrategyVerdictState.UNAVAILABLE,
    ):
        assessment = _assessment()

        result = apply_selected_strategy_gate(
            assessment,
            _verdict(state),
            mode=MethodologyGateMode.ENFORCE,
        )

        assert result.changed is False
        assert result.assessment is assessment
        assert result.assessment.setup is not None
        assert result.reason_codes == ("METHODOLOGY_GATE_NO_CHANGE",)
