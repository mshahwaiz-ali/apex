"""Tests for the immutable futures lifecycle state machine."""

from datetime import UTC, datetime, timedelta

import pytest

from apex.domain import (
    TradeLifecycle,
    TradeLifecycleEvent,
    TradeLifecycleEventType,
    TradeLifecycleState,
    replay_lifecycle_events,
)


def _time(minutes: int = 0) -> datetime:
    return datetime(2026, 7, 13, 12, 0, tzinfo=UTC) + timedelta(minutes=minutes)


def test_generated_plan_can_wait_then_enter() -> None:
    lifecycle = TradeLifecycle(created_at=_time(), updated_at=_time())

    waiting = lifecycle.transition(TradeLifecycleState.WAITING_FOR_ENTRY, at=_time(1))
    entered = waiting.transition(TradeLifecycleState.ENTERED, at=_time(2))

    assert waiting.state is TradeLifecycleState.WAITING_FOR_ENTRY
    assert entered.state is TradeLifecycleState.ENTERED
    assert entered.entered_at == _time(2)


def test_entered_trade_can_partially_close_then_hit_target() -> None:
    lifecycle = TradeLifecycle(created_at=_time(), updated_at=_time())
    entered = lifecycle.transition(TradeLifecycleState.ENTERED, at=_time(1))
    partial = entered.transition(
        TradeLifecycleState.PARTIALLY_CLOSED,
        at=_time(2),
        closed_percentage=60,
    )
    closed = partial.transition(TradeLifecycleState.TARGET_HIT, at=_time(3))

    assert partial.closed_percentage == 60
    assert closed.closed_percentage == 100
    assert closed.closed_at == _time(3)


def test_terminal_state_rejects_further_transitions() -> None:
    lifecycle = TradeLifecycle(created_at=_time(), updated_at=_time())
    expired = lifecycle.transition(TradeLifecycleState.EXPIRED, at=_time(1))

    with pytest.raises(ValueError, match="invalid lifecycle transition"):
        expired.transition(TradeLifecycleState.ENTERED, at=_time(2))


def test_closed_percentage_cannot_decrease() -> None:
    lifecycle = TradeLifecycle(created_at=_time(), updated_at=_time())
    entered = lifecycle.transition(TradeLifecycleState.ENTERED, at=_time(1))
    partial = entered.transition(
        TradeLifecycleState.PARTIALLY_CLOSED,
        at=_time(2),
        closed_percentage=60,
    )

    with pytest.raises(ValueError, match="cannot decrease"):
        partial.transition(
            TradeLifecycleState.PARTIALLY_CLOSED,
            at=_time(3),
            closed_percentage=40,
        )


def test_transition_time_cannot_move_backward() -> None:
    lifecycle = TradeLifecycle(created_at=_time(), updated_at=_time())
    waiting = lifecycle.transition(TradeLifecycleState.WAITING_FOR_ENTRY, at=_time(2))

    with pytest.raises(ValueError, match="cannot precede"):
        waiting.transition(TradeLifecycleState.ENTERED, at=_time(1))


def test_lifecycle_events_replay_partial_and_full_target() -> None:
    lifecycle = replay_lifecycle_events(
        created_at=_time(),
        events=(
            TradeLifecycleEvent(
                event_type=TradeLifecycleEventType.ENTRY_FILLED,
                occurred_at=_time(1),
            ),
            TradeLifecycleEvent(
                event_type=TradeLifecycleEventType.PARTIAL_TARGET_HIT,
                occurred_at=_time(2),
                closed_percentage=50,
            ),
            TradeLifecycleEvent(
                event_type=TradeLifecycleEventType.FULL_TARGET_HIT,
                occurred_at=_time(3),
            ),
        ),
    )

    assert lifecycle.state is TradeLifecycleState.TARGET_HIT
    assert lifecycle.closed_percentage == 100
    assert lifecycle.entered_at == _time(1)
    assert lifecycle.closed_at == _time(3)


def test_lifecycle_events_replay_runner_trailing_and_stop_updates() -> None:
    lifecycle = replay_lifecycle_events(
        created_at=_time(),
        events=(
            TradeLifecycleEvent(
                event_type=TradeLifecycleEventType.ENTRY_FILLED,
                occurred_at=_time(1),
            ),
            TradeLifecycleEvent(
                event_type=TradeLifecycleEventType.PARTIAL_TARGET_HIT,
                occurred_at=_time(2),
                closed_percentage=50,
                target_label="tp1",
            ),
            TradeLifecycleEvent(
                event_type=TradeLifecycleEventType.STOP_MOVED_TO_BREAKEVEN,
                occurred_at=_time(3),
                stop_price=100,
            ),
            TradeLifecycleEvent(
                event_type=TradeLifecycleEventType.RUNNER_ACTIVATED,
                occurred_at=_time(4),
            ),
            TradeLifecycleEvent(
                event_type=TradeLifecycleEventType.TRAILING_STOP_UPDATED,
                occurred_at=_time(5),
                trailing_stop_price=102,
            ),
        ),
    )

    assert lifecycle.state is TradeLifecycleState.PARTIALLY_CLOSED
    assert lifecycle.closed_percentage == 50
    assert lifecycle.partial_targets_hit == ("tp1",)
    assert lifecycle.active_stop_price == 100
    assert lifecycle.runner_active is True
    assert lifecycle.trailing_stop_price == 102
    assert lifecycle.updated_at == _time(5)


def test_partial_target_event_requires_closed_percentage() -> None:
    with pytest.raises(ValueError, match="partial target"):
        TradeLifecycleEvent(
            event_type=TradeLifecycleEventType.PARTIAL_TARGET_HIT,
            occurred_at=_time(1),
        )


def test_stop_movement_event_requires_stop_price() -> None:
    with pytest.raises(ValueError, match="stop movement"):
        TradeLifecycleEvent(
            event_type=TradeLifecycleEventType.STOP_MOVED_TO_BREAKEVEN,
            occurred_at=_time(1),
        )


def test_trailing_stop_event_requires_trailing_stop_price() -> None:
    with pytest.raises(ValueError, match="trailing stop"):
        TradeLifecycleEvent(
            event_type=TradeLifecycleEventType.TRAILING_STOP_UPDATED,
            occurred_at=_time(1),
        )


def test_replay_rejects_invalid_event_transition() -> None:
    with pytest.raises(ValueError, match="invalid lifecycle transition"):
        replay_lifecycle_events(
            created_at=_time(),
            events=(
                TradeLifecycleEvent(
                    event_type=TradeLifecycleEventType.PARTIAL_TARGET_HIT,
                    occurred_at=_time(1),
                    closed_percentage=50,
                ),
            ),
        )


def test_trade_management_event_before_entry_is_rejected() -> None:
    with pytest.raises(ValueError, match="entered trade"):
        replay_lifecycle_events(
            created_at=_time(),
            events=(
                TradeLifecycleEvent(
                    event_type=TradeLifecycleEventType.RUNNER_ACTIVATED,
                    occurred_at=_time(1),
                ),
            ),
        )


def test_terminal_state_rejects_followup_metadata_event() -> None:
    with pytest.raises(ValueError, match="terminal lifecycle"):
        replay_lifecycle_events(
            created_at=_time(),
            events=(
                TradeLifecycleEvent(
                    event_type=TradeLifecycleEventType.ENTRY_FILLED,
                    occurred_at=_time(1),
                ),
                TradeLifecycleEvent(
                    event_type=TradeLifecycleEventType.FULL_TARGET_HIT,
                    occurred_at=_time(2),
                ),
                TradeLifecycleEvent(
                    event_type=TradeLifecycleEventType.RUNNER_ACTIVATED,
                    occurred_at=_time(3),
                ),
            ),
        )
