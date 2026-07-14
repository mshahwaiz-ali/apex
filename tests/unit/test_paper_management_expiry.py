"""Focused tests for explicit paper expiry and lifecycle-derived guidance."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apex.backtesting import BacktestSignal
from apex.domain import CurrentAction, TradeLifecycleEventType
from apex.paper_trading import (
    PaperTrade,
    PaperTradeState,
    derive_paper_trade_guidance,
    expire_waiting_trade,
    paper_entry_expiry,
)
from apex.strategies import StrategyType, TradeDirection


NOW = datetime(2026, 7, 14, 10, 0, tzinfo=UTC)
EXPIRY = NOW + timedelta(minutes=15)


def _signal() -> BacktestSignal:
    return BacktestSignal(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=NOW,
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        quantity=1.0,
        risk_amount=2.0,
        confidence_score=80.0,
        target_prices=(102.0, 104.0),
        partial_close_percentages=(50.0, 50.0),
    )


def _plan() -> dict[str, object]:
    return {
        "management_plan": {
            "entry": {"expires_at": EXPIRY.isoformat()},
            "initial_protection": {"stop_loss_price": 98.0},
            "targets": [
                {"label": "tp1", "price": 102.0},
                {"label": "tp2", "price": 104.0},
            ],
        }
    }


def _waiting_trade() -> PaperTrade:
    return PaperTrade(
        trade_id="paper-expiry",
        signal=_signal(),
        state=PaperTradeState.WAITING_FOR_ENTRY,
        created_at=NOW,
        updated_at=NOW,
        analysis_payload={},
        futures_plan=_plan(),
        lifecycle_events=(
            {
                "event_type": TradeLifecycleEventType.SETUP_GENERATED.value,
                "occurred_at": NOW.isoformat(),
            },
            {
                "event_type": TradeLifecycleEventType.WAITING_FOR_ENTRY.value,
                "occurred_at": NOW.isoformat(),
            },
        ),
    )


def test_explicit_entry_expiry_is_read_and_enforced() -> None:
    trade = _waiting_trade()

    assert paper_entry_expiry(trade) == EXPIRY
    assert expire_waiting_trade(trade, at=EXPIRY - timedelta(seconds=1)) is trade

    expired = expire_waiting_trade(trade, at=EXPIRY)
    assert expired.state is PaperTradeState.EXPIRED
    assert expired.exit_time == EXPIRY
    assert expired.lifecycle_events[-1]["event_type"] == TradeLifecycleEventType.EXPIRED.value
    assert derive_paper_trade_guidance(expired).current_action is CurrentAction.DO_NOT_ENTER


def test_runner_and_trailing_stop_are_reported_from_lifecycle_replay() -> None:
    entered_at = NOW + timedelta(minutes=1)
    trailing_at = NOW + timedelta(minutes=5)
    trade = PaperTrade(
        trade_id="paper-runner",
        signal=_signal(),
        state=PaperTradeState.ENTERED,
        created_at=NOW,
        updated_at=trailing_at,
        analysis_payload={},
        futures_plan=_plan(),
        lifecycle_events=(
            {
                "event_type": TradeLifecycleEventType.SETUP_GENERATED.value,
                "occurred_at": NOW.isoformat(),
            },
            {
                "event_type": TradeLifecycleEventType.WAITING_FOR_ENTRY.value,
                "occurred_at": NOW.isoformat(),
            },
            {
                "event_type": TradeLifecycleEventType.ENTRY_FILLED.value,
                "occurred_at": entered_at.isoformat(),
            },
            {
                "event_type": TradeLifecycleEventType.RUNNER_ACTIVATED.value,
                "occurred_at": (NOW + timedelta(minutes=4)).isoformat(),
                "runner_active": True,
            },
            {
                "event_type": TradeLifecycleEventType.TRAILING_STOP_UPDATED.value,
                "occurred_at": trailing_at.isoformat(),
                "trailing_stop_price": 101.0,
            },
        ),
        entry_time=entered_at,
        entry_price=100.0,
    )

    guidance = derive_paper_trade_guidance(trade)
    assert guidance.current_action is CurrentAction.MOVE_STOP
    assert guidance.runner_active is True
    assert guidance.trailing_stop_price == 101.0
    assert guidance.active_stop_price == 101.0
    assert "never loosen" in guidance.instruction
