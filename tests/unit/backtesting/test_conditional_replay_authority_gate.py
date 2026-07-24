from dataclasses import replace
from datetime import UTC, datetime

from apex.application.discovery_contracts import (
    ActionableEntry,
    ActivationTrigger,
    ActivationTriggerType,
    ConditionalExecutionPlan,
    DiscoverySetup,
    ExecutionAuthority,
    ManagementPolicy,
    ManagementPolicyType,
    PreEntryInvalidation,
    RecommendedOrderIntent,
    SetupValidity,
    StopLoss,
    TakeProfit,
)
from apex.cli_commands.backtesting import _conditional_replay_authorized
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


def _setup(*, future_activation_allowed: bool) -> DiscoverySetup:
    conditional_plan = ConditionalExecutionPlan(
        trigger=ActivationTrigger(
            kind=ActivationTriggerType.CANDLE_CLOSE,
            level=100.0,
            condition="confirm",
            confirmation_timeframe="5m",
        ),
        pre_entry_invalidation=PreEntryInvalidation(
            price=102.0,
            condition="invalidate",
            rationale=("structure",),
        ),
        conditional_order_eligible=False,
        recommended_order_intent=RecommendedOrderIntent.ALERT_ONLY,
        reason_not_executable_now="pending confirmation",
        geometry_basis="test",
        entry_source="test",
        trigger_matches_preferred_entry=True,
        stop_basis="test",
        targets_basis="test",
        geometry_is_trigger_relative=True,
    )
    return DiscoverySetup(
        symbol="TEST/USDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.TREND_PULLBACK,
        entry_status=EntryStatus.CONFIRMATION_AT_CMP,
        decision_time=datetime(2026, 1, 1, tzinfo=UTC),
        candidate_id="trend_pullback:long:0",
        confidence_score=60.0,
        entry=ActionableEntry(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=100.0,
            maximum_chase_price=101.5,
            current_price_inside_zone=True,
        ),
        stop_loss=StopLoss(
            price=98.0,
            distance=2.0,
            distance_pct=2.0,
            rationale=("structure",),
        ),
        take_profits=(
            TakeProfit(
                label="TP1",
                price=104.0,
                reward=4.0,
                risk_reward=2.0,
                rationale=("structure",),
            ),
        ),
        management_policies=(
            ManagementPolicy(
                kind=ManagementPolicyType.TIME_EXIT,
                trigger="holding window expires",
                action="close remaining position",
                rationale=("test lifecycle policy",),
            ),
        ),
        warnings=(),
        execution_allowed_now=False,
        future_activation_allowed=future_activation_allowed,
        setup_validity=SetupValidity.VALID,
        execution_authority=(
            ExecutionAuthority.CONDITIONAL_FUTURE
            if future_activation_allowed
            else ExecutionAuthority.MONITOR_ONLY
        ),
        conditional_plan=conditional_plan,
    )


def test_future_authorized_setup_enters_conditional_replay() -> None:
    assert _conditional_replay_authorized(_setup(future_activation_allowed=True))


def test_monitor_only_setup_cannot_enter_conditional_replay() -> None:
    assert not _conditional_replay_authorized(_setup(future_activation_allowed=False))


def test_missing_conditional_plan_cannot_enter_conditional_replay() -> None:
    setup = replace(
        _setup(future_activation_allowed=True),
        future_activation_allowed=False,
        execution_authority=ExecutionAuthority.MONITOR_ONLY,
        conditional_plan=None,
    )
    assert not _conditional_replay_authorized(setup)
