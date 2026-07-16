"""Tests for account-aware paper portfolio accounting."""

from __future__ import annotations

from datetime import UTC, datetime

from apex.backtesting import BacktestSignal
from apex.paper_trading.contracts import PaperTrade, PaperTradeState
from apex.paper_trading.portfolio import (
    build_paper_portfolio_snapshot,
    paper_portfolio_payload,
)
from apex.strategies import StrategyType, TradeDirection

_NOW = datetime(2026, 7, 16, tzinfo=UTC)


def _trade(
    *,
    trade_id: str,
    state: PaperTradeState,
    net_pnl: float = 0.0,
    closed_percentage: float = 0.0,
    margin: float = 100.0,
    risk: float = 20.0,
) -> PaperTrade:
    signal = BacktestSignal(
        symbol=f"{trade_id}USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=_NOW,
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        quantity=10.0,
        risk_amount=risk,
        confidence_score=80.0,
        target_prices=(102.0, 104.0),
        partial_close_percentages=(50.0, 50.0),
    )
    terminal = state in {
        PaperTradeState.STOPPED,
        PaperTradeState.TARGET_HIT,
        PaperTradeState.EXPIRED,
        PaperTradeState.CANCELLED,
        PaperTradeState.INVALIDATED,
    }
    return PaperTrade(
        trade_id=trade_id,
        signal=signal,
        state=state,
        created_at=_NOW,
        updated_at=_NOW,
        analysis_payload={"market_type": "futures"},
        futures_plan={
            "required_margin": margin,
            "total_maximum_planned_loss": risk,
        },
        entry_time=_NOW if state in {PaperTradeState.ENTERED, PaperTradeState.PARTIALLY_CLOSED} else None,
        entry_price=100.0 if state in {PaperTradeState.ENTERED, PaperTradeState.PARTIALLY_CLOSED} else None,
        exit_time=_NOW if terminal else None,
        exit_price=101.0 if terminal else None,
        net_pnl=net_pnl,
        realized_r_multiple=net_pnl / risk if terminal else 0.0,
        closed_percentage=closed_percentage,
        notes=("portfolio fixture",),
    )


def test_entered_trade_reserves_margin_and_open_risk() -> None:
    snapshot = build_paper_portfolio_snapshot(
        (_trade(trade_id="entered", state=PaperTradeState.ENTERED),),
        initial_wallet_balance=1000.0,
    )

    assert snapshot.wallet_equity == 1000.0
    assert snapshot.reserved_margin == 100.0
    assert snapshot.available_balance == 900.0
    assert snapshot.open_risk == 20.0
    assert snapshot.wallet_exposure_pct == 10.0
    assert snapshot.entered_trade_count == 1
    assert not snapshot.locked


def test_partial_close_reduces_remaining_open_risk() -> None:
    snapshot = build_paper_portfolio_snapshot(
        (
            _trade(
                trade_id="partial",
                state=PaperTradeState.PARTIALLY_CLOSED,
                closed_percentage=50.0,
            ),
        ),
        initial_wallet_balance=1000.0,
    )

    assert snapshot.reserved_margin == 100.0
    assert snapshot.open_risk == 10.0


def test_terminal_pnl_updates_equity_without_reserving_margin() -> None:
    snapshot = build_paper_portfolio_snapshot(
        (
            _trade(
                trade_id="closed",
                state=PaperTradeState.TARGET_HIT,
                net_pnl=50.0,
                closed_percentage=100.0,
            ),
        ),
        initial_wallet_balance=1000.0,
    )

    payload = paper_portfolio_payload(snapshot)
    assert snapshot.realized_net_pnl == 50.0
    assert snapshot.wallet_equity == 1050.0
    assert snapshot.reserved_margin == 0.0
    assert snapshot.open_trade_count == 0
    assert payload["wallet_equity"] == 1050.0


def test_exposure_and_open_risk_limits_lock_portfolio() -> None:
    snapshot = build_paper_portfolio_snapshot(
        (_trade(trade_id="locked", state=PaperTradeState.ENTERED, margin=600.0, risk=100.0),),
        initial_wallet_balance=1000.0,
        maximum_wallet_exposure_pct=50.0,
        maximum_open_risk_pct=5.0,
    )

    assert snapshot.locked
    assert snapshot.lock_reasons == (
        "wallet exposure limit exceeded",
        "open risk limit exceeded",
    )
