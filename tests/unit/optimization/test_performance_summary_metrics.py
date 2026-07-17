"""Tests for complete historical performance metric adaptation."""

from __future__ import annotations

import pytest

from apex.optimization.engine import performance_from_campaign_payload, performance_from_mapping


def test_performance_mapping_preserves_existing_backtest_metrics() -> None:
    summary = performance_from_mapping(
        {
            "metrics": {
                "total_trades": 10,
                "win_rate": 0.4,
                "loss_rate": 0.5,
                "expectancy": 1.25,
                "profit_factor": 1.8,
                "maximum_drawdown": 4.0,
                "net_profit": 12.5,
                "average_win": 5.0,
                "average_loss": -2.0,
            }
        }
    )

    assert summary.loss_rate == pytest.approx(0.5)
    assert summary.average_win == pytest.approx(5.0)
    assert summary.average_loss == pytest.approx(-2.0)


def test_performance_mapping_keeps_new_metrics_backward_compatible() -> None:
    summary = performance_from_mapping({"metrics": {"total_trades": 1}})

    assert summary.loss_rate == 0.0
    assert summary.average_win == 0.0
    assert summary.average_loss == 0.0


def test_campaign_payload_aggregates_win_and_loss_averages() -> None:
    summary = performance_from_campaign_payload(
        {
            "best_variant_id": "candidate",
            "variants": [
                {
                    "variant": {"identifier": "candidate"},
                    "symbol": "BTCUSDT",
                    "metrics": {
                        "total_trades": 10,
                        "win_rate": 0.4,
                        "loss_rate": 0.5,
                        "gross_profit": 20.0,
                        "gross_loss": -10.0,
                    },
                },
                {
                    "variant": {"identifier": "candidate"},
                    "symbol": "ETHUSDT",
                    "metrics": {
                        "total_trades": 10,
                        "win_rate": 0.6,
                        "loss_rate": 0.3,
                        "gross_profit": 30.0,
                        "gross_loss": -6.0,
                    },
                },
            ],
        }
    )

    assert summary.loss_rate == pytest.approx(0.4)
    assert summary.average_win == pytest.approx(5.0)
    assert summary.average_loss == pytest.approx(-2.0)
