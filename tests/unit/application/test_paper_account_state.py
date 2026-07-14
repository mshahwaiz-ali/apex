from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from apex.application.account_state import AccountStateSnapshot
from apex.application.paper_account_state import (
    PaperAccountExposure,
    apply_paper_account_transition,
    attach_account_state_registration,
)
from apex.backtesting import BacktestSignal
from apex.paper_trading import PaperTrade, PaperTradeState
from apex.strategies import StrategyType, TradeDirection


def _snapshot(*, consecutive_losses: int = 0) -> AccountStateSnapshot:
    return AccountStateSnapshot(
        policy_name="PAPER",
        trading_day=date(2026, 7, 14),
        current_balance=1000.0,
        current_equity=1000.0,
        start_of_day_equity=1000.0,
        consecutive_losses=consecutive_losses,
    )


def _trade(*, state: PaperTradeState = PaperTradeState.WAITING_FOR_ENTRY) -> PaperTrade:
    timestamp = datetime(2026, 7, 14, 8, 0, tzinfo=UTC)
    signal = BacktestSignal(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=timestamp,
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        quantity=1.0,
        risk_amount=2.0,
        confidence_score=80.0,
        target_prices=(102.0, 104.0),
        partial_close_percentages=(50.0, 50.0),
    )
    plan = attach_account_state_registration(
        {"status": "APPROVED"},
        PaperAccountExposure(policy_name="PAPER", risk_pct=0.5),
    )
    return PaperTrade(
        trade_id="paper-1",
        signal=signal,
        state=state,
        created_at=timestamp,
        updated_at=timestamp,
        analysis_payload={},
        futures_plan=plan,
    )


def test_entry_registers_daily_trade_and_open_risk() -> None:
    before = _trade()
    after = replace(
        before,
        state=PaperTradeState.ENTERED,
        entry_time=before.created_at,
        entry_price=100.0,
    )

    updated = apply_paper_account_transition(_snapshot(), before, after)

    assert updated.trades_today == 1
    assert updated.total_open_risk_pct == 0.5
    assert updated.directional_exposure_pct == 0.0
    assert updated.correlated_exposure_pct == 0.0


def test_partial_close_releases_only_closed_open_risk() -> None:
    before = replace(
        _trade(),
        state=PaperTradeState.ENTERED,
        entry_time=datetime(2026, 7, 14, 8, 5, tzinfo=UTC),
        entry_price=100.0,
    )
    after = replace(
        before,
        state=PaperTradeState.PARTIALLY_CLOSED,
        closed_percentage=50.0,
        partial_target_count=1,
        net_pnl=1.0,
    )
    opened = _snapshot().register_entry(
        risk_pct=0.5,
        directional_risk_pct=0.0,
        correlated_risk_pct=0.0,
    )

    updated = apply_paper_account_transition(opened, before, after)

    assert updated.total_open_risk_pct == 0.25
    assert updated.current_balance == 1000.0
    assert updated.consecutive_losses == 0


def test_terminal_loss_releases_remaining_risk_and_updates_loss_streak() -> None:
    entered_at = datetime(2026, 7, 14, 8, 5, tzinfo=UTC)
    before = replace(
        _trade(),
        state=PaperTradeState.PARTIALLY_CLOSED,
        entry_time=entered_at,
        entry_price=100.0,
        closed_percentage=50.0,
        partial_target_count=1,
        net_pnl=1.0,
    )
    after = replace(
        before,
        state=PaperTradeState.STOPPED,
        updated_at=datetime(2026, 7, 14, 8, 10, tzinfo=UTC),
        exit_time=datetime(2026, 7, 14, 8, 10, tzinfo=UTC),
        exit_price=98.0,
        closed_percentage=100.0,
        net_pnl=-1.5,
        realized_r_multiple=-0.75,
    )
    opened = (
        _snapshot()
        .register_entry(
            risk_pct=0.5,
            directional_risk_pct=0.0,
            correlated_risk_pct=0.0,
        )
        .release_exposure(
            released_risk_pct=0.25,
            released_directional_risk_pct=0.0,
            released_correlated_risk_pct=0.0,
        )
    )

    updated = apply_paper_account_transition(opened, before, after)

    assert updated.total_open_risk_pct == 0.0
    assert updated.current_balance == 998.5
    assert updated.current_equity == 998.5
    assert updated.consecutive_losses == 1


def test_terminal_profit_resets_existing_loss_streak() -> None:
    before = replace(
        _trade(),
        state=PaperTradeState.ENTERED,
        entry_time=datetime(2026, 7, 14, 8, 5, tzinfo=UTC),
        entry_price=100.0,
    )
    after = replace(
        before,
        state=PaperTradeState.TARGET_HIT,
        updated_at=datetime(2026, 7, 14, 8, 10, tzinfo=UTC),
        exit_time=datetime(2026, 7, 14, 8, 10, tzinfo=UTC),
        exit_price=104.0,
        closed_percentage=100.0,
        partial_target_count=2,
        net_pnl=3.5,
        realized_r_multiple=1.75,
    )
    opened = _snapshot(consecutive_losses=2).register_entry(
        risk_pct=0.5,
        directional_risk_pct=0.0,
        correlated_risk_pct=0.0,
    )

    updated = apply_paper_account_transition(opened, before, after)

    assert updated.total_open_risk_pct == 0.0
    assert updated.current_balance == 1003.5
    assert updated.consecutive_losses == 0


def test_trade_without_registration_metadata_does_not_change_state() -> None:
    before = replace(_trade(), futures_plan={"status": "APPROVED"})
    after = replace(
        before,
        state=PaperTradeState.ENTERED,
        entry_time=before.created_at,
        entry_price=100.0,
    )
    snapshot = _snapshot()

    assert apply_paper_account_transition(snapshot, before, after) == snapshot
