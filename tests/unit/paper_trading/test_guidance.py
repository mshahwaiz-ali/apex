"""Tests for lifecycle-backed paper-trade guidance."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest

from apex.domain import CurrentAction
from apex.paper_trading import (
    PaperTradeState,
    build_paper_guidance_report,
    derive_paper_trade_guidance,
)


def _trade(
    state: PaperTradeState,
    *,
    partial_target_count: int = 0,
    entry_price: float | None = None,
) -> Any:
    return SimpleNamespace(
        trade_id="paper-1",
        state=state,
        partial_target_count=partial_target_count,
        entry_price=entry_price,
        signal=SimpleNamespace(symbol="BTCUSDT"),
        futures_plan={
            "management_plan": {
                "initial_protection": {"stop_loss_price": 98.0},
                "targets": [
                    {"label": "TP1", "price": 103.0},
                    {"label": "TP2", "price": 106.0},
                ],
            }
        },
    )


def test_waiting_trade_reports_wait_and_first_target() -> None:
    guidance = derive_paper_trade_guidance(cast(Any, _trade(PaperTradeState.WAITING_FOR_ENTRY)))

    assert guidance.current_action is CurrentAction.WAIT
    assert guidance.active_stop_price == 98.0
    assert guidance.next_target_label == "TP1"
    assert guidance.next_target_price == 103.0


def test_entered_trade_reports_hold() -> None:
    guidance = derive_paper_trade_guidance(cast(Any, _trade(PaperTradeState.ENTERED)))

    assert guidance.current_action is CurrentAction.HOLD
    assert guidance.completed_targets == ()


def test_partial_trade_moves_stop_and_advances_target() -> None:
    guidance = derive_paper_trade_guidance(
        cast(
            Any,
            _trade(
                PaperTradeState.PARTIALLY_CLOSED,
                partial_target_count=1,
                entry_price=100.5,
            ),
        )
    )

    assert guidance.current_action is CurrentAction.MOVE_STOP
    assert guidance.active_stop_price == 100.5
    assert guidance.completed_targets == ("TP1",)
    assert guidance.next_target_label == "TP2"


@pytest.mark.parametrize(
    ("state", "action"),
    [
        (PaperTradeState.INVALIDATED, CurrentAction.CANCEL_SETUP),
        (PaperTradeState.CANCELLED, CurrentAction.CANCEL_SETUP),
        (PaperTradeState.EXPIRED, CurrentAction.DO_NOT_ENTER),
        (PaperTradeState.STOPPED, CurrentAction.CLOSE_ALL),
        (PaperTradeState.TARGET_HIT, CurrentAction.CLOSE_ALL),
    ],
)
def test_terminal_states_have_unambiguous_actions(
    state: PaperTradeState,
    action: CurrentAction,
) -> None:
    guidance = derive_paper_trade_guidance(cast(Any, _trade(state)))

    assert guidance.current_action is action
    assert guidance.next_target_label is None


def test_guidance_report_is_stable_and_requires_aware_time() -> None:
    trade = cast(Any, _trade(PaperTradeState.ENTERED))
    timestamp = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)

    report = build_paper_guidance_report((trade,), generated_at=timestamp)

    assert report["schema_version"] == 1
    assert report["trade_count"] == 1
    assert report["trades"][0]["current_action"] == "HOLD"
    with pytest.raises(ValueError, match="timezone-aware"):
        build_paper_guidance_report((trade,), generated_at=datetime(2026, 7, 14, 12, 0))
