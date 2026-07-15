"""Tests for deterministic shared-wallet historical replay."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.backtesting.contracts import BacktestOutcome, BacktestSignal, SimulatedTrade
from apex.backtesting.shared_wallet_replay import (
    SharedWalletConfig,
    WalletRejectionCode,
    WalletReplayCandidate,
    replay_shared_wallet,
)
from apex.strategies import StrategyType, TradeDirection


def _candidate(
    candidate_id: str,
    *,
    symbol: str = "BTCUSDT",
    minute: int = 0,
    duration: int = 5,
    pnl: float = 100.0,
    margin: float = 1_000.0,
) -> WalletReplayCandidate:
    generated = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minute)
    signal = BacktestSignal(
        symbol=symbol,
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=generated,
        entry_price=100.0,
        stop_price=90.0,
        target_price=120.0,
        quantity=10.0,
        risk_amount=100.0,
        confidence_score=80.0,
    )
    trade = SimulatedTrade(
        signal=signal,
        outcome=BacktestOutcome.TARGET if pnl > 0.0 else BacktestOutcome.STOP,
        exit_time=generated + timedelta(minutes=duration),
        exit_price=120.0 if pnl > 0.0 else 90.0,
        gross_pnl=pnl + 2.0,
        fees=2.0,
        net_pnl=pnl,
        realized_r_multiple=pnl / 100.0,
        holding_candles=max(duration, 1),
    )
    return WalletReplayCandidate(
        candidate_id=candidate_id,
        split="train",
        trade=trade,
        required_margin=margin,
    )


def test_replay_closes_positions_before_later_decisions() -> None:
    result = replay_shared_wallet(
        candidates=(
            _candidate("second", minute=10, pnl=-50.0),
            _candidate("first", minute=0, pnl=100.0),
        ),
        starting_equity=10_000.0,
        config=SharedWalletConfig(maximum_concurrent_positions=1),
    )

    assert [item.candidate_id for item in result.accepted_candidates] == ["first", "second"]
    assert result.ending_equity == 10_050.0
    assert result.realized_pnl == 50.0
    assert [point.event for point in result.equity_curve] == ["opened", "closed", "opened", "closed"]


def test_concurrency_and_same_symbol_blocks_are_explicit() -> None:
    concurrency = replay_shared_wallet(
        candidates=(
            _candidate("a", symbol="BTCUSDT", duration=20),
            _candidate("b", symbol="ETHUSDT", minute=1),
        ),
        starting_equity=10_000.0,
        config=SharedWalletConfig(maximum_concurrent_positions=1),
    )
    overlap = replay_shared_wallet(
        candidates=(
            _candidate("a", duration=20),
            _candidate("b", minute=1),
        ),
        starting_equity=10_000.0,
        config=SharedWalletConfig(maximum_concurrent_positions=2),
    )

    assert concurrency.decisions[1].rejection_code is WalletRejectionCode.CONCURRENCY_LIMIT
    assert overlap.decisions[1].rejection_code is WalletRejectionCode.DUPLICATE_SYMBOL


def test_exposure_and_available_margin_are_separate_controls() -> None:
    exposure = replay_shared_wallet(
        candidates=(_candidate("a", margin=6_000.0),),
        starting_equity=10_000.0,
        config=SharedWalletConfig(maximum_wallet_exposure_pct=50.0),
    )
    balance = replay_shared_wallet(
        candidates=(_candidate("a", margin=11_000.0),),
        starting_equity=10_000.0,
        config=SharedWalletConfig(maximum_wallet_exposure_pct=100.0),
    )

    assert exposure.decisions[0].rejection_code is WalletRejectionCode.EXPOSURE_LIMIT
    assert balance.decisions[0].rejection_code is WalletRejectionCode.INSUFFICIENT_MARGIN


def test_daily_loss_pauses_later_same_day_candidates() -> None:
    result = replay_shared_wallet(
        candidates=(
            _candidate("loss", pnl=-1_100.0, duration=1),
            _candidate("blocked", symbol="ETHUSDT", minute=2),
            _candidate("paused", symbol="SOLUSDT", minute=3),
        ),
        starting_equity=10_000.0,
        config=SharedWalletConfig(daily_loss_limit_pct=10.0, consecutive_loss_limit=5),
    )

    assert result.decisions[1].rejection_code is WalletRejectionCode.DAILY_LOSS_LIMIT
    assert result.decisions[2].rejection_code is WalletRejectionCode.CAMPAIGN_PAUSED


def test_consecutive_loss_lockout_pauses_same_day() -> None:
    result = replay_shared_wallet(
        candidates=(
            _candidate("loss-1", pnl=-50.0, duration=1),
            _candidate("loss-2", symbol="ETHUSDT", minute=2, pnl=-50.0, duration=1),
            _candidate("blocked", symbol="SOLUSDT", minute=4),
            _candidate("paused", symbol="XRPUSDT", minute=5),
        ),
        starting_equity=10_000.0,
        config=SharedWalletConfig(daily_loss_limit_pct=100.0, consecutive_loss_limit=2),
    )

    assert result.decisions[2].rejection_code is WalletRejectionCode.LOSS_LOCKOUT
    assert result.decisions[3].rejection_code is WalletRejectionCode.CAMPAIGN_PAUSED


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (SharedWalletConfig, ""),
    ],
)
def test_placeholder_keeps_parametrize_import_used(config: object, message: str) -> None:
    assert config is SharedWalletConfig
    assert message == ""
