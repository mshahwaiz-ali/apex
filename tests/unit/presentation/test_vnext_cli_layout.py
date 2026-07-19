"""Regression tests for the action-first public CLI layout."""

from __future__ import annotations

from apex.presentation.backtest_output import render_backtest, render_campaign
from apex.presentation.methodology_selected_entry_output import render_discovery_analysis
from apex.presentation.system import render_config, render_version


def test_explained_analysis_uses_sections_instead_of_raw_json() -> None:
    rendered = render_discovery_analysis(
        {
            "symbol": "BTC/USDT",
            "candidate_count": 0,
            "reasons": ["no valid setup formed"],
            "market_intelligence": {"early_warning": {"state": "neutral"}},
        },
        explain=True,
    )

    assert "┌─ Decision" in rendered
    assert "Full Diagnostics" not in rendered
    assert '"market_intelligence"' not in rendered


def test_backtest_report_is_action_first_and_grouped() -> None:
    rendered = render_backtest(
        {
            "symbol": "BTC/USDT",
            "replay_timeframe": "5m",
            "decision_point_count": 5,
            "generated_signal_count": 3,
            "no_trade_decision_count": 2,
            "metrics": {
                "total_trades": 3,
                "win_rate": 2 / 3,
                "expectancy": 0.25,
                "net_profit": 1.5,
                "profit_factor": 1.8,
                "average_win": 1.0,
                "average_loss": -0.5,
                "maximum_drawdown": 0.5,
            },
            "promotion_statistics": {
                "deflated_sharpe_probability": 0.7,
                "probability_backtest_overfitting": 0.2,
            },
            "study": {"skipped_signal_count": 0, "dataset_hash": "a" * 64},
        }
    )

    assert "APEX BACKTEST" in rendered
    assert "Performance after modeled costs" in rendered
    assert "Robustness checks" in rendered
    assert "| expectancy=" not in rendered


def test_campaign_config_and_version_have_clear_cards() -> None:
    campaign = render_campaign(
        {
            "months": ["2026-01", "2026-02"],
            "symbol_count": 30,
            "verified_file_count": 180,
            "missing_file_count": 0,
            "manifest": "data/campaign_manifest.json",
            "manifest_hash": "b" * 64,
            "model_training": "not requested",
        }
    )
    config = render_config(
        {
            "environment": "development",
            "analysis_timeframes": ["5m", "1h"],
            "timeframe_roles": {"5m": "entry"},
            "strategy_routing": {"enabled": True},
            "futures_screener": {"shortlist": 30},
            "methodology_gate_mode": "shadow",
            "data_dir": "data",
            "cache_enabled": True,
            "futures_evidence_enabled": True,
            "outcome_tracking_enabled": True,
        }
    )

    assert "Campaign status" in campaign
    assert "CONFIGURATION IS VALID" in config
    assert "Installed build" in render_version("1.2.3")
