"""Tests for trader-facing futures simulation presentation."""

from __future__ import annotations

from apex.presentation.simulation import render_futures_simulation


def _completed_payload() -> dict[str, object]:
    return {
        "trade": {
            "signal": {
                "symbol": "BTCUSDT",
                "strategy": "breakout_retest",
                "direction": "long",
                "entry_price": 100.0,
                "stop_price": 98.0,
                "target_price": 104.0,
                "target_prices": [102.0, 104.0],
                "partial_close_percentages": [50.0, 50.0],
                "quantity": 2.0,
                "risk_amount": 4.0,
                "confidence_score": 82.5,
            },
            "outcome": "target",
            "exit_time": "2026-07-16T12:00:00+00:00",
            "exit_price": 104.0,
            "gross_pnl": 8.0,
            "fees": 0.16,
            "net_pnl": 7.84,
            "realized_r_multiple": 1.96,
            "holding_candles": 6,
            "metadata": {"exit_reason": "target", "fee_pct": 0.04, "slippage_pct": 0.02},
        },
        "metrics": {"total_trades": 1},
    }


def test_completed_simulation_is_trader_facing() -> None:
    rendered = render_futures_simulation(_completed_payload())

    assert "Futures Setup Simulation — BTCUSDT" in rendered
    assert "Setup available" in rendered
    assert "Direction" in rendered
    assert "Long" in rendered
    assert "Breakout retest" in rendered
    assert "TP1: 102.0000" in rendered
    assert "Simulated Outcome" in rendered
    assert "Net PnL" in rendered
    assert "Realized R" in rendered
    assert "Risk Impact" in rendered
    assert "Simulation Assumptions" in rendered
    assert "net_pnl=" not in rendered


def test_no_setup_simulation_explains_rejection() -> None:
    rendered = render_futures_simulation(
        {
            "symbol": "ETHUSDT",
            "decision": "NO_BACKTEST",
            "reasons": ["Price is too extended for a controlled entry"],
        }
    )

    assert "Futures Setup Simulation — ETHUSDT" in rendered
    assert "Setup available: No" in rendered
    assert "Price is too extended for a controlled entry" in rendered
    assert "NO_BACKTEST" not in rendered


def test_default_simulation_includes_assumptions() -> None:
    rendered = render_futures_simulation(_completed_payload())

    assert "Simulation Assumptions" in rendered
    assert "Fee rate" in rendered
    assert "Slippage modeled" in rendered
