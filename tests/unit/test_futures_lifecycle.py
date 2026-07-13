"""Tests for the immutable futures lifecycle state machine."""

from datetime import UTC, datetime, timedelta

import pytest

from apex.domain import TradeLifecycle, TradeLifecycleState


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
