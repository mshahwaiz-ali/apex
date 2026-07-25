from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from types import MappingProxyType

from apex.backtesting.contracts import BacktestOutcome, BacktestSignal, SimulatedTrade
from apex.backtesting.engine import summarize_trades
from apex.cli_commands.backtesting import (
    _activation_metrics,
    _canonical_trade_records,
    _decision_funnel_metrics,
    _execution_metrics,
    _filled_execution_trades,
    _outcome_distribution,
    _replay_outcomes_by_decision,
    _report_metrics,
    _risk_and_excursion,
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
    mfe_r: float | None = None,
    mae_r: float | None = None,
    path_mfe_r: float | None = None,
    path_mae_r: float | None = None,
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
                **({"maximum_favorable_excursion_r": mfe_r} if mfe_r is not None else {}),
                **({"maximum_adverse_excursion_r": mae_r} if mae_r is not None else {}),
                **({"counterfactual_path_mfe_r": path_mfe_r} if path_mfe_r is not None else {}),
                **({"counterfactual_path_mae_r": path_mae_r} if path_mae_r is not None else {}),
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


def test_filled_execution_population_excludes_unfilled_lifecycle_records() -> None:
    filled = _trade(
        "filled",
        outcome=BacktestOutcome.TARGET,
        net_pnl=4.0,
        entry_filled=True,
        terminal_state="target",
        activation_outcome="triggered",
    )
    expired = _trade(
        "expired",
        outcome=BacktestOutcome.ACTIVATION_EXPIRED,
        net_pnl=0.0,
        entry_filled=False,
        terminal_state="never_activated",
        activation_outcome="activation_expired",
    )

    assert _filled_execution_trades((filled, expired)) == (filled,)


def test_public_report_metrics_use_filled_trades_only() -> None:
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

    metrics = _report_metrics(summarize_trades(_filled_execution_trades((filled, unfilled))))

    assert metrics["total_trades"] == 1
    assert metrics["win_rate"] == 1.0
    assert metrics["loss_rate"] == 0.0
    assert metrics["net_profit"] == 4.0
    assert metrics["expectancy"] == 4.0


def test_risk_excursion_separates_filled_and_counterfactual_populations() -> None:
    filled = _trade(
        "filled",
        outcome=BacktestOutcome.TARGET,
        net_pnl=4.0,
        entry_filled=True,
        terminal_state="target",
        activation_outcome="triggered",
        mfe_r=2.0,
        mae_r=0.5,
        path_mfe_r=2.5,
        path_mae_r=0.7,
    )
    unfilled = _trade(
        "expired",
        outcome=BacktestOutcome.ACTIVATION_EXPIRED,
        net_pnl=0.0,
        entry_filled=False,
        terminal_state="never_activated",
        activation_outcome="activation_expired",
        mfe_r=9.0,
        mae_r=8.0,
        path_mfe_r=3.5,
        path_mae_r=1.3,
    )

    metrics = _risk_and_excursion((filled, unfilled))

    assert metrics["filled_trade_count"] == 1
    assert metrics["average_mfe_r"] == 2.0
    assert metrics["average_mae_r"] == 0.5
    assert metrics["best_mfe_r"] == 2.0
    assert metrics["worst_mae_r"] == 0.5
    assert metrics["counterfactual_path_count"] == 2
    assert metrics["average_counterfactual_path_mfe_r"] == 3.0
    assert metrics["average_counterfactual_path_mae_r"] == 1.0


def test_production_replay_precedes_conditional_at_same_decision_time() -> None:
    production = _trade(
        "production",
        outcome=BacktestOutcome.TARGET,
        net_pnl=4.0,
        entry_filled=True,
        terminal_state="target",
        activation_outcome="triggered",
    )
    conditional = _trade(
        "conditional",
        outcome=BacktestOutcome.STOP,
        net_pnl=-2.0,
        entry_filled=True,
        terminal_state="stop",
        activation_outcome="triggered",
    )

    outcomes = _replay_outcomes_by_decision(
        production_trades=(production,),
        conditional_trades=(conditional,),
        replay_record=lambda trade, replay_class: {
            "outcome": trade.outcome.value,
            "replay_class": replay_class,
        },
    )

    decision_time = production.signal.generated_at.isoformat()
    assert outcomes[decision_time] == {
        "outcome": BacktestOutcome.TARGET.value,
        "replay_class": "production",
    }


def test_conditional_replay_fills_timestamp_without_production_result() -> None:
    conditional = _trade(
        "conditional",
        outcome=BacktestOutcome.TARGET,
        net_pnl=3.0,
        entry_filled=True,
        terminal_state="target",
        activation_outcome="triggered",
    )

    outcomes = _replay_outcomes_by_decision(
        production_trades=(),
        conditional_trades=(conditional,),
        replay_record=lambda trade, replay_class: {
            "outcome": trade.outcome.value,
            "replay_class": replay_class,
        },
    )

    decision_time = conditional.signal.generated_at.isoformat()
    assert outcomes[decision_time]["replay_class"] == "conditional"


def test_outcome_distribution_uses_separate_lifecycle_and_fill_denominators() -> None:
    target = _trade(
        "target",
        outcome=BacktestOutcome.TARGET,
        net_pnl=4.0,
        entry_filled=True,
        terminal_state="target",
        activation_outcome="triggered",
    )
    target = replace(
        target,
        metadata=MappingProxyType(
            {
                **target.metadata,
                "partial_target_count": 2,
                "net_profitable_target": True,
            }
        ),
    )
    stop = _trade(
        "stop",
        outcome=BacktestOutcome.STOP,
        net_pnl=-2.0,
        entry_filled=True,
        terminal_state="stop",
        activation_outcome="triggered",
    )
    missed = _trade(
        "missed",
        outcome=BacktestOutcome.MISSED_ENTRY,
        net_pnl=0.0,
        entry_filled=False,
        terminal_state="missed_trigger",
        activation_outcome="maximum_chase_breached",
    )
    invalidated = _trade(
        "invalidated",
        outcome=BacktestOutcome.PRE_ENTRY_INVALIDATED,
        net_pnl=0.0,
        entry_filled=False,
        terminal_state="pre_entry_invalidated",
        activation_outcome="pre_entry_invalidated",
    )

    metrics = _outcome_distribution((target, stop, missed, invalidated))

    assert metrics["signal_outcome_count"] == 4
    assert metrics["filled_trade_count"] == 2
    assert metrics["stop_rate"] == 0.5
    assert metrics["tp1_hit_rate"] == 0.5
    assert metrics["tp2_hit_rate"] == 0.5
    assert metrics["missed_entry_rate"] == 0.25
    assert metrics["pre_entry_invalidation_rate"] == 0.25


def test_decision_funnel_deduplicates_overlapping_replay_lanes() -> None:
    production = _trade(
        "production",
        outcome=BacktestOutcome.TARGET,
        net_pnl=4.0,
        entry_filled=True,
        terminal_state="target",
        activation_outcome="triggered",
    )
    conditional = _trade(
        "conditional",
        outcome=BacktestOutcome.STOP,
        net_pnl=-2.0,
        entry_filled=True,
        terminal_state="stop",
        activation_outcome="triggered",
    )

    metrics = _decision_funnel_metrics(
        decision_point_count=1,
        production_signals=1,
        conditional_signals=1,
        no_trade_decisions=[],
        production_trades=(production,),
        conditional_trades=(conditional,),
    )

    assert metrics["raw_immediate_signal_count"] == 1
    assert metrics["raw_conditional_signal_count"] == 1
    assert metrics["overlapping_setup_decision_count"] == 1
    assert metrics["immediate_setup_count"] == 1
    assert metrics["future_setup_count"] == 0
    assert metrics["setup_found_count"] == 1
    assert metrics["setup_coverage_rate"] == 1.0
    assert metrics["immediate_fill_count"] == 1
    assert metrics["future_fill_count"] == 0
    assert metrics["total_fill_count"] == 1


def test_trade_records_expose_replay_provenance_and_canonical_authority() -> None:
    trade = _trade(
        "production",
        outcome=BacktestOutcome.TARGET,
        net_pnl=4.0,
        entry_filled=True,
        terminal_state="target",
        activation_outcome="triggered",
    )

    records = _canonical_trade_records(
        (trade,),
        calibration_records=[],
        partition_by_time={},
        fee_pct=0.0,
        slippage_pct=0.0,
    )

    assert records[0]["replay_source"] == "production"
    assert records[0]["replay_class"] == "production"
    assert records[0]["canonical_portfolio"] is True


def test_trade_record_calibration_join_prefers_candidate_identity() -> None:
    trade = _trade(
        "candidate-b",
        outcome=BacktestOutcome.TARGET,
        net_pnl=4.0,
        entry_filled=True,
        terminal_state="target",
        activation_outcome="triggered",
    )
    calibration_records = [
        {
            "decision_time": NOW.isoformat(),
            "candidate_id": "candidate-a",
            "opportunity_id": "candidate-a",
            "sequence_role": "primary",
            "actionability_state": "ready_now",
            "replay_reason_code": "candidate_a",
            "canonical_portfolio": True,
            "setup_geometry_fingerprint": ["long", "primary", 99.0],
        },
        {
            "decision_time": NOW.isoformat(),
            "candidate_id": "candidate-b",
            "opportunity_id": "candidate-b",
            "sequence_role": "alternative",
            "actionability_state": "wait_for_close",
            "replay_reason_code": "candidate_b",
            "canonical_portfolio": False,
            "setup_geometry_fingerprint": ["long", "alternative", 100.0],
        },
    ]

    records = _canonical_trade_records(
        (trade,),
        calibration_records=calibration_records,
        partition_by_time={NOW.isoformat(): "validation"},
        fee_pct=0.0,
        slippage_pct=0.0,
    )

    assert records[0]["opportunity_id"] == "candidate-b"
    assert records[0]["sequence_role"] == "alternative"
    assert records[0]["actionability_state"] == "wait_for_close"
    assert records[0]["replay_reason_code"] == "candidate_b"
    assert records[0]["canonical_portfolio"] is False
    assert records[0]["setup_geometry_fingerprint"] == [
        "long",
        "alternative",
        100.0,
    ]
