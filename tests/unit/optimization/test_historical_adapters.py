from __future__ import annotations

import pytest

from apex.optimization import (
    performance_from_futures_historical_payload,
    performance_from_spot_historical_payload,
)


def test_spot_historical_payload_adapter_preserves_breakdown_counts() -> None:
    summary = performance_from_spot_historical_payload(
        {
            "metrics": {
                "trade_count": 5,
                "win_rate": 0.6,
                "expectancy": 12.5,
                "profit_factor": 1.8,
                "maximum_drawdown": 0.08,
                "net_profit": 62.5,
                "performance_by_symbol": {
                    "BTCUSDT": {"trade_count": 3},
                    "ETHUSDT": {"trade_count": 2},
                },
                "performance_by_strategy": {
                    "trend_pullback": {"trade_count": 5}
                },
                "performance_by_market_regime": {
                    "risk_on": {"trade_count": 4},
                    "range": {"trade_count": 1},
                },
            }
        }
    )

    assert summary.total_trades == 5
    assert summary.expectancy == 12.5
    assert summary.by_symbol == {"BTCUSDT": 3, "ETHUSDT": 2}
    assert summary.by_strategy == {"trend_pullback": 5}
    assert summary.by_regime == {"risk_on": 4, "range": 1}


def test_futures_historical_payload_adapter_selects_requested_split() -> None:
    summary = performance_from_futures_historical_payload(
        {
            "split_metrics": {
                "train": {"total_trades": 20, "expectancy": 1.0},
                "validation": {
                    "trade_count": 8,
                    "win_rate": 0.5,
                    "expectancy": 0.4,
                    "profit_factor": 1.2,
                    "maximum_drawdown": 0.1,
                    "net_profit": 3.2,
                    "performance_by_symbol": {
                        "BTCUSDT": {"trade_count": 4},
                        "ETHUSDT": {"trade_count": 4},
                    },
                },
            }
        },
        split="validation",
    )

    assert summary.total_trades == 8
    assert summary.expectancy == 0.4
    assert summary.by_symbol == {"BTCUSDT": 4, "ETHUSDT": 4}


def test_futures_historical_payload_adapter_rejects_missing_split() -> None:
    with pytest.raises(ValueError, match="does not contain split: final_test"):
        performance_from_futures_historical_payload(
            {"split_metrics": {"train": {"total_trades": 1}}},
            split="final_test",
        )
