"""Tests for deterministic trade lifecycle execution and reporting."""

from datetime import UTC, datetime, timedelta

from apex.application.trade_lifecycle_engine import (
    LifecycleObservation,
    replay_trade_lifecycle,
)
from apex.application.trade_lifecycle_reporting import (
    format_trade_lifecycle,
    trade_lifecycle_payload,
)
from apex.domain import (
    CurrentAction,
    EmergencyExitRule,
    EntryInstruction,
    EntryInstructionAction,
    EntryState,
    FuturesDirection,
    InitialProtectionInstruction,
    ManagementTarget,
    ManagementTriggerType,
    RecommendedOrderType,
    StopInstructionType,
    TradeLifecycleEventType,
    TradeLifecycleState,
    TradeManagementPlan,
)


def _plan() -> TradeManagementPlan:
    return TradeManagementPlan(
        direction=FuturesDirection.LONG,
        entry=EntryInstruction(
            action=EntryInstructionAction.ENTER_NOW,
            entry_state=EntryState.READY_NOW,
            zone_low=99.8,
            zone_high=100.2,
            ideal_entry=100.0,
            maximum_chase_price=100.5,
            order_type=RecommendedOrderType.MARKET,
            cancellation_conditions=("cancel on invalidation",),
        ),
        initial_protection=InitialProtectionInstruction(
            stop_loss_price=99.0,
            stop_type=StopInstructionType.STOP_MARKET,
            risk_percentage=1.0,
            risk_amount=10.0,
            quantity=10.0,
            notional=1000.0,
            margin=100.0,
            leverage=10.0,
            estimated_fees=0.0,
            estimated_slippage=0.0,
            estimated_liquidation_price=91.0,
            stop_to_liquidation_buffer=8.0,
        ),
        targets=(
            ManagementTarget(
                label="TP1",
                price=101.0,
                close_percentage=50.0,
                cumulative_close_percentage=50.0,
                expected_r_multiple=1.0,
                rationale="first target",
            ),
            ManagementTarget(
                label="TP2",
                price=102.0,
                close_percentage=50.0,
                cumulative_close_percentage=100.0,
                expected_r_multiple=2.0,
                rationale="second target",
            ),
        ),
        emergency_exits=(
            EmergencyExitRule(
                trigger_type=ManagementTriggerType.STRUCTURAL_BREAK,
                condition="close on structural break",
            ),
        ),
        current_action=CurrentAction.ENTER,
    )


def _observation(at: datetime, *, high: float, low: float, close: float, momentum_failed: bool = False) -> LifecycleObservation:
    return LifecycleObservation(
        observed_at=at,
        high=high,
        low=low,
        close=close,
        momentum_failed=momentum_failed,
    )


def test_tp1_moves_stop_activates_runner_and_momentum_exit_closes() -> None:
    start = datetime(2026, 7, 16, tzinfo=UTC)
    execution = replay_trade_lifecycle(
        _plan(),
        (
            _observation(start, high=100.2, low=99.9, close=100.1),
            _observation(start + timedelta(minutes=1), high=101.2, low=100.4, close=101.0),
            _observation(
                start + timedelta(minutes=2),
                high=101.1,
                low=100.5,
                close=100.7,
                momentum_failed=True,
            ),
        ),
        created_at=start,
    )

    event_types = tuple(event.event_type for event in execution.events)
    assert TradeLifecycleEventType.ENTRY_FILLED in event_types
    assert TradeLifecycleEventType.PARTIAL_TARGET_HIT in event_types
    assert TradeLifecycleEventType.STOP_MOVED_TO_BREAKEVEN in event_types
    assert TradeLifecycleEventType.RUNNER_ACTIVATED in event_types
    assert TradeLifecycleEventType.MOMENTUM_FAILURE_EXIT in event_types
    assert execution.lifecycle.state is TradeLifecycleState.STOPPED
    assert execution.remaining_percentage == 0.0
    assert execution.exit_reason == "momentum failure"


def test_structural_invalidation_before_entry_cancels_setup() -> None:
    start = datetime(2026, 7, 16, tzinfo=UTC)
    execution = replay_trade_lifecycle(
        _plan(),
        (_observation(start, high=99.4, low=98.8, close=99.1),),
        created_at=start,
    )

    assert execution.entry_price is None
    assert execution.lifecycle.state is TradeLifecycleState.INVALIDATED
    assert execution.events[0].event_type is TradeLifecycleEventType.STRUCTURAL_INVALIDATION


def test_time_exit_is_preserved_in_execution_log_and_closes_snapshot() -> None:
    start = datetime(2026, 7, 16, tzinfo=UTC)
    execution = replay_trade_lifecycle(
        _plan(),
        (
            _observation(start, high=100.2, low=99.9, close=100.1),
            _observation(start + timedelta(minutes=1), high=100.6, low=99.9, close=100.4),
        ),
        created_at=start,
        maximum_open_bars=2,
    )

    assert execution.events[-1].event_type is TradeLifecycleEventType.TIME_EXIT
    assert execution.lifecycle.state is TradeLifecycleState.STOPPED
    assert execution.exit_reason == "time exit"


def test_reporting_contains_execution_metrics() -> None:
    start = datetime(2026, 7, 16, tzinfo=UTC)
    execution = replay_trade_lifecycle(
        _plan(),
        (
            _observation(start, high=100.2, low=99.9, close=100.1),
            _observation(start + timedelta(minutes=1), high=102.2, low=100.4, close=102.0),
        ),
        created_at=start,
    )

    payload = trade_lifecycle_payload(execution)
    text = format_trade_lifecycle(execution)

    assert payload["state"] == TradeLifecycleState.TARGET_HIT.value
    assert payload["remaining_percentage"] == 0.0
    assert "Lifecycle state: TARGET_HIT" in text
    assert "Realized R:" in text
