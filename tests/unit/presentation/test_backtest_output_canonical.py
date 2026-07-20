from __future__ import annotations

from types import SimpleNamespace

from apex.cli_commands.backtesting import _outcome_distribution, _risk_and_excursion
from apex.presentation.backtest_output import render_backtest


def _trade(outcome: str, targets: int, mfe: float, mae: float) -> object:
    return SimpleNamespace(
        outcome=SimpleNamespace(value=outcome),
        metadata={
            "partial_target_count": targets,
            "maximum_favorable_excursion_r": mfe,
            "maximum_adverse_excursion_r": mae,
        },
    )


def test_backtest_aggregates_existing_outcome_and_excursion_facts() -> None:
    trades = (
        _trade("target", 3, 3.0, 0.2),
        _trade("stop", 1, 1.0, 1.1),
        _trade("missed_entry", 0, 0.0, 0.0),
    )

    outcomes = _outcome_distribution(trades)
    excursions = _risk_and_excursion(trades)

    assert outcomes["target"] == 1
    assert outcomes["stop"] == 1
    assert outcomes["missed_entry"] == 1
    assert outcomes["tp1_hit_count"] == 2
    assert outcomes["tp2_hit_count"] == 1
    assert outcomes["tp3_hit_count"] == 1
    assert excursions["best_mfe_r"] == 3.0
    assert excursions["worst_mae_r"] == 1.1


def test_backtest_renderer_shows_complete_canonical_sections() -> None:
    rendered = render_backtest(
        {
            "symbol": "BTCUSDT",
            "replay_timeframe": "5m",
            "replay_candles": 24,
            "decision_point_count": 2,
            "generated_signal_count": 1,
            "no_trade_decision_count": 1,
            "execution_assumptions": {
                "fee_pct": 0.04,
                "slippage_pct": 0.02,
                "funding_pct": 0.0,
                "maximum_holding_candles": 24,
                "methodology_gate_mode": "enforce",
            },
            "metrics": {
                "total_trades": 1,
                "win_rate": 1.0,
                "expectancy": 1.2,
                "net_profit": 1.2,
                "profit_factor": None,
                "average_risk_reward": 1.2,
                "maximum_drawdown": 0.0,
            },
            "outcome_distribution": {
                "target": 1,
                "stop": 0,
                "expired": 0,
                "missed_entry": 0,
                "tp1_hit_rate": 1.0,
                "tp2_hit_rate": 1.0,
                "tp3_hit_rate": 0.0,
                "stop_rate": 0.0,
            },
            "risk_and_excursion": {
                "average_mfe_r": 2.0,
                "average_mae_r": 0.2,
                "best_mfe_r": 2.0,
                "worst_mae_r": 0.2,
            },
            "metrics_by_partition": {
                "training": {},
                "validation": {},
                "final_test": {"total_trades": 1, "expectancy": 1.2},
            },
            "trades": [
                {
                    "trade_number": 1,
                    "decision_time": "2026-07-20T12:00:00+00:00",
                    "opportunity_id": "btc-current",
                    "sequence_role": "current",
                    "actionability_state": "execute_now",
                    "outcome": "target",
                    "realized_r_multiple": 1.2,
                    "net_pnl": 1.2,
                    "maximum_favorable_excursion_r": 2.0,
                    "maximum_adverse_excursion_r": 0.2,
                    "partition": "final_test",
                    "signal": {
                        "symbol": "BTCUSDT",
                        "direction": "long",
                        "strategy": "breakout_retest",
                        "entry_price": 100.0,
                        "stop_price": 95.0,
                        "target_prices": [110.0],
                    },
                }
            ],
            "no_trade_decisions": [
                {
                    "decision_time": "2026-07-20T13:00:00+00:00",
                    "reason_code": "canonical_opportunity_not_executable",
                }
            ],
            "promotion_statistics": {},
            "study": {
                "skipped_signal_count": 0,
                "dataset_hash": "a" * 64,
                "config_hash": "b" * 64,
                "code_hash": "c" * 64,
            },
        }
    )

    for heading in (
        "Test configuration",
        "Outcome distribution",
        "Risk and excursion",
        "Partition performance",
        "Trade record",
        "No-trade decisions",
    ):
        assert heading in rendered
    assert "btc-current" in rendered
    assert "canonical_opportunity_not_executable" in rendered
