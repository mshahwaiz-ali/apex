from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.backtesting import (
    BacktestOutcome,
    BacktestSignal,
    DrawdownAcceptanceReport,
    SimulatedTrade,
    drawdown_acceptance_payload,
    evaluate_drawdown_acceptance,
    summarize_trades,
)
from apex.strategies import StrategyType, TradeDirection


def _report():
    return summarize_trades(
        (
            _trade(index=0, net_pnl=10.0),
            _trade(index=1, net_pnl=-6.0),
            _trade(index=2, net_pnl=-3.0),
        )
    )


def _trade(*, index: int, net_pnl: float) -> SimulatedTrade:
    signal = BacktestSignal(
        symbol=f"DRAWDOWN{index}USDT",
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        direction=TradeDirection.LONG,
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        entry_price=100.0,
        stop_price=95.0,
        target_price=110.0,
        quantity=1.0,
        risk_amount=5.0,
        confidence_score=70.0,
    )
    outcome = BacktestOutcome.TARGET if net_pnl > 0.0 else BacktestOutcome.STOP
    return SimulatedTrade(
        signal=signal,
        outcome=outcome,
        exit_time=datetime(2026, 1, 2, tzinfo=UTC),
        exit_price=110.0 if net_pnl > 0.0 else 95.0,
        gross_pnl=net_pnl,
        fees=0.0,
        net_pnl=net_pnl,
        realized_r_multiple=net_pnl / 5.0,
        holding_candles=2,
    )


def test_drawdown_policy_is_unavailable_without_explicit_limit() -> None:
    report = evaluate_drawdown_acceptance(_report(), maximum_drawdown_limit=None)
    payload = drawdown_acceptance_payload(report)

    assert report.observed_maximum_drawdown == pytest.approx(9.0)
    assert report.acceptable_drawdown is None
    assert report.blocker == "drawdown_policy_unavailable"
    assert payload["maximum_drawdown_limit"] is None


def test_drawdown_is_accepted_only_when_within_explicit_limit() -> None:
    report = evaluate_drawdown_acceptance(_report(), maximum_drawdown_limit=9.0)

    assert report.acceptable_drawdown is True
    assert report.blocker is None


def test_drawdown_exceeding_explicit_limit_is_rejected() -> None:
    report = evaluate_drawdown_acceptance(_report(), maximum_drawdown_limit=8.5)

    assert report.acceptable_drawdown is False
    assert report.blocker == "drawdown_exceeds_limit"


def test_drawdown_policy_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        DrawdownAcceptanceReport(
            observed_maximum_drawdown=1.0,
            maximum_drawdown_limit=-1.0,
            acceptable_drawdown=False,
            blocker="drawdown_exceeds_limit",
        )
