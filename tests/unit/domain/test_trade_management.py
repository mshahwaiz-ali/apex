"""Tests for canonical manual trade-management contracts."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

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
    StopManagementRule,
    TradeManagementPlan,
    entry_action_for_state,
    lifecycle_event_for_action,
    replay_lifecycle_events,
)

NOW = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)


def _entry(
    *,
    action: EntryInstructionAction = EntryInstructionAction.ENTER_NOW,
    state: EntryState = EntryState.READY_NOW,
    order_type: RecommendedOrderType = RecommendedOrderType.MARKET,
) -> EntryInstruction:
    return EntryInstruction(
        action=action,
        entry_state=state,
        zone_low=100.0,
        zone_high=101.0,
        ideal_entry=100.5,
        maximum_chase_price=101.5,
        order_type=order_type,
        cancellation_conditions=("price crosses structural invalidation",),
    )


def _protection() -> InitialProtectionInstruction:
    return InitialProtectionInstruction(
        stop_loss_price=98.0,
        stop_type=StopInstructionType.STOP_MARKET,
        risk_percentage=0.25,
        risk_amount=2.5,
        quantity=0.5,
        notional=50.0,
        margin=10.0,
        leverage=5.0,
        estimated_fees=0.05,
        estimated_slippage=0.05,
        estimated_liquidation_price=81.0,
        stop_to_liquidation_buffer=17.0,
    )


def _targets() -> tuple[ManagementTarget, ...]:
    return (
        ManagementTarget(
            label="TP1",
            price=103.0,
            close_percentage=60.0,
            cumulative_close_percentage=60.0,
            expected_r_multiple=1.0,
            rationale="first opposing liquidity",
        ),
        ManagementTarget(
            label="TP2",
            price=106.0,
            close_percentage=40.0,
            cumulative_close_percentage=100.0,
            expected_r_multiple=2.2,
            rationale="higher-timeframe resistance",
        ),
    )


def _plan() -> TradeManagementPlan:
    return TradeManagementPlan(
        direction=FuturesDirection.LONG,
        entry=_entry(),
        initial_protection=_protection(),
        targets=_targets(),
        stop_management=(
            StopManagementRule(
                trigger_type=ManagementTriggerType.TARGET_FILLED,
                trigger_reference="TP1",
                action=CurrentAction.MOVE_STOP,
                stop_price=100.5,
                instruction="move stop to breakeven after TP1 is confirmed",
            ),
        ),
        emergency_exits=(
            EmergencyExitRule(
                trigger_type=ManagementTriggerType.STRUCTURAL_BREAK,
                condition="close below structural invalidation",
            ),
        ),
        current_action=CurrentAction.ENTER,
    )


def test_complete_management_plan_serializes_to_json() -> None:
    payload = _plan().model_dump(mode="json")

    assert payload["current_action"] == "ENTER"
    assert payload["entry"]["action"] == "ENTER_NOW"
    assert payload["targets"][1]["cumulative_close_percentage"] == 100.0


def test_target_percentages_must_total_one_hundred() -> None:
    targets = list(_targets())
    targets[1] = targets[1].model_copy(
        update={
            "close_percentage": 30.0,
            "cumulative_close_percentage": 90.0,
        }
    )

    with pytest.raises(ValidationError, match="percentages must total 100"):
        _plan().model_copy(update={"targets": tuple(targets)}).model_validate(
            {
                **_plan().model_dump(),
                "targets": [target.model_dump() for target in targets],
            }
        )


def test_short_targets_must_decrease() -> None:
    with pytest.raises(ValidationError, match="short targets must decrease"):
        TradeManagementPlan(
            direction=FuturesDirection.SHORT,
            entry=_entry(),
            initial_protection=_protection(),
            targets=_targets(),
            emergency_exits=_plan().emergency_exits,
            current_action=CurrentAction.ENTER,
        )


def test_enter_action_requires_actionable_entry_instruction() -> None:
    with pytest.raises(ValidationError, match="ENTER requires"):
        TradeManagementPlan(
            direction=FuturesDirection.LONG,
            entry=_entry(
                action=EntryInstructionAction.WAIT_FOR_RETEST,
                state=EntryState.WAIT_FOR_RETEST,
                order_type=RecommendedOrderType.LIMIT,
            ),
            initial_protection=_protection(),
            targets=_targets(),
            emergency_exits=_plan().emergency_exits,
            current_action=CurrentAction.ENTER,
        )


@pytest.mark.parametrize(
    ("state", "entry_action", "current_action"),
    [
        (EntryState.READY_NOW, EntryInstructionAction.ENTER_NOW, CurrentAction.ENTER),
        (
            EntryState.WAIT_FOR_RETEST,
            EntryInstructionAction.WAIT_FOR_RETEST,
            CurrentAction.WAIT,
        ),
        (
            EntryState.WAIT_FOR_RECLAIM,
            EntryInstructionAction.WAIT_FOR_RECLAIM,
            CurrentAction.WAIT,
        ),
        (
            EntryState.MISSED_ENTRY,
            EntryInstructionAction.REJECT,
            CurrentAction.DO_NOT_ENTER,
        ),
        (
            EntryState.INVALIDATED,
            EntryInstructionAction.REJECT,
            CurrentAction.DO_NOT_ENTER,
        ),
    ],
)
def test_entry_state_mapping_is_deterministic(
    state: EntryState,
    entry_action: EntryInstructionAction,
    current_action: CurrentAction,
) -> None:
    assert entry_action_for_state(state) == (entry_action, current_action)


def test_management_actions_replay_through_existing_lifecycle() -> None:
    entry_event = lifecycle_event_for_action(CurrentAction.ENTER, occurred_at=NOW)
    partial_event = lifecycle_event_for_action(
        CurrentAction.PARTIAL_CLOSE,
        occurred_at=NOW + timedelta(minutes=5),
        target_label="TP1",
        closed_percentage=60.0,
    )

    assert entry_event is not None
    assert partial_event is not None
    lifecycle = replay_lifecycle_events(
        created_at=NOW - timedelta(minutes=1),
        events=(entry_event, partial_event),
    )

    assert lifecycle.state.value == "PARTIALLY_CLOSED"
    assert lifecycle.closed_percentage == 60.0
    assert lifecycle.partial_targets_hit == ("TP1",)


def test_wait_and_hold_do_not_emit_lifecycle_events() -> None:
    assert lifecycle_event_for_action(CurrentAction.WAIT, occurred_at=NOW) is None
    assert lifecycle_event_for_action(CurrentAction.HOLD, occurred_at=NOW) is None
