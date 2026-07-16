"""Regression tests for paper presentation field lookup."""

from __future__ import annotations

from apex.presentation.paper import _first, render_paper_trade


def test_first_checks_all_keys_in_declared_order() -> None:
    plan = {"ideal_entry": 101.0}
    signal = {"entry_price": 100.0}

    assert _first(plan, signal, "entry_price", "ideal_entry") == 100.0


def test_first_checks_sources_in_declared_order() -> None:
    plan = {"quantity": 2.0}
    signal = {"quantity": 1.0}

    assert _first(plan, signal, "quantity") == 2.0


def test_first_preserves_zero_and_false_values() -> None:
    primary = {"zero": 0, "disabled": False}

    assert _first(primary, "zero") == 0
    assert _first(primary, "disabled") is False


def test_first_returns_none_when_no_key_exists() -> None:
    assert _first({"entry_price": None}, {}, "entry_price", "ideal_entry") is None


def test_trade_renderer_uses_primary_and_fallback_plan_fields() -> None:
    rendered = render_paper_trade(
        {
            "result": "opened",
            "trade": {
                "trade_id": "paper-1",
                "state": "ENTERED",
                "signal": {
                    "symbol": "BTC/USDT",
                    "direction": "long",
                    "entry_price": 100.0,
                    "stop_price": 95.0,
                    "quantity": 0.25,
                },
                "futures_plan": {
                    "ideal_entry": 101.0,
                    "stop_loss": 94.0,
                    "required_margin": 12.5,
                    "wallet_exposure_pct": 0.125,
                    "maximum_modeled_loss": 2.5,
                    "selected_leverage": 10,
                },
            },
        }
    )

    assert "Entry" in rendered and ": 100" in rendered
    assert "Stop" in rendered and ": 95" in rendered
    assert "Quantity" in rendered and ": 0.25" in rendered
    assert "Margin" in rendered and ": 12.50" in rendered
    assert "Leverage" in rendered and ": 10x" in rendered
