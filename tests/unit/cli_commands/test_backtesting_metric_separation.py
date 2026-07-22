from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType

from apex.backtesting.contracts import BacktestOutcome, BacktestSignal, SimulatedTrade
from apex.cli_commands.backtesting import (
    _activation_metrics,
    _decision_funnel_metrics,
    _execution_metrics,
)
from apex.strategies import StrategyType, TradeDirection

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)


def _signal(candidate_id: str) -> BacktestSignal:
    return BacktestSignal(
        symbol="BTCUSDT",
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        direction=TradeDirection.LONG,
        generated_at=NOW,
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        quantity=1.0,
        risk_amount=2.0,
        confidence_score=80.0,
        candidate_id=candidate_id,
    )


def _trade(
    candidate_id: str,
    *,
    outcome: BacktestOutcome,
    net_pnl: float,
    entry_filled: bool,
    terminal_state: str,
    activation_outcome: str,
) -> SimulatedTrade:
    return SimulatedTrade(
        signal=_signal(candidate_id),
        outcome=outcome,
        exit_time=NOW,
        exit_price=104.0 if net_pnl > 0 else 100.0,
        gross_pnl=net_pnl,
        fees=0.0,
        net_pnl=net_pnl,
        realized_r_multiple=net_pnl / 2.0,
        holding_candles=1,
        metadata=MappingProxyType(
            {
                "entry_filled": entry_filled,
                "terminal_state": terminal_state,
                "activation_outcome": activation_outcome,
                "activation_wait_candles": 1,
            }
        ),
    )


def test_execution_metrics_exclude_unfilled_future_plans() -> None:
    filled = _trade(
        "filled",
        outcome=BacktestOutcome.TARGET,
        net_pnl=4.0,
        entry_filled=True,
        terminal_state="target",
        activation_outcome="triggered",
    )
    unfilled = _trade(
        "expired",
        outcome=BacktestOutcome.ACTIVATION_EXPIRED,
        net_pnl=0.0,
        entry_filled=False,
        terminal_state="never_activated",
        activation_outcome="activation_expired",
    )

    metrics = _execution_metrics((filled, unfilled))

    assert metrics["signal_outcome_count"] == 2
    assert metrics["filled_trade_count"] == 1
    assert metrics["fill_rate"] == 0.5
    assert metrics["win_rate"] == 1.0


def test_activation_metrics_do_not_mix_activation_with_trade_results() -> None:
    activated = _trade(
        "activated",
        outcome=BacktestOutcome.TARGET,
        net_pnl=4.0,
        entry_filled=True,
        terminal_state="target",
        activation_outcome="triggered",
    )
    invalidated = _trade(
        "invalidated",
        outcome=BacktestOutcome.PRE_ENTRY_INVALIDATED,
        net_pnl=0.0,
        entry_filled=False,
        terminal_state="pre_entry_invalidated",
        activation_outcome="pre_entry_invalidated",
    )

    metrics = _activation_metrics((activated, invalidated))

    assert metrics["future_setup_count"] == 2
    assert metrics["activation_count"] == 1
    assert metrics["activation_rate"] == 0.5
    assert metrics["fill_count"] == 1
    assert metrics["pre_entry_invalidation_count"] == 1


def test_decision_funnel_separates_future_setups_from_true_no_setup() -> None:
    filled = _trade(
        "filled",
        outcome=BacktestOutcome.TARGET,
        net_pnl=4.0,
        entry_filled=True,
        terminal_state="target",
        activation_outcome="triggered",
    )
    decisions = [
        {"reasons": ["canonical_opportunity_pending_activation"]},
        {"reasons": ["canonical_no_executable_opportunity"]},
    ]

    metrics = _decision_funnel_metrics(
        decision_point_count=3,
        production_signals=1,
        conditional_signals=1,
        no_trade_decisions=decisions,
        production_trades=(filled,),
        conditional_trades=(),
    )

    assert metrics["setup_found_count"] == 2
    assert metrics["true_no_setup_count"] == 1
    assert metrics["setup_coverage_rate"] == 2 / 3
