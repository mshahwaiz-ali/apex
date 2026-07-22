from __future__ import annotations

from datetime import UTC, datetime

from apex.backtesting.contracts import BacktestSignal
from apex.cli_commands.backtesting import (
    _confirmation_diagnostics,
    _enriched_trade_diagnostics,
    _r_progress_diagnostics,
    _tp1_approached_before_stop,
)
from apex.strategies import StrategyType, TradeDirection


def test_backtest_signal_freezes_diagnostics() -> None:
    source = {"entry_confirmation_complete": True}
    signal = BacktestSignal(
        symbol="BTC/USDT",
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        direction=TradeDirection.LONG,
        generated_at=datetime(2026, 7, 22, tzinfo=UTC),
        entry_price=100.0,
        stop_price=99.0,
        target_price=102.0,
        quantity=1.0,
        risk_amount=1.0,
        confidence_score=60.0,
        diagnostics=source,
    )
    source["entry_confirmation_complete"] = False
    assert signal.diagnostics["entry_confirmation_complete"] is True


def test_confirmation_diagnostics_preserves_nested_facts() -> None:
    result = _confirmation_diagnostics(
        {
            "candidate": {
                "entry_confirmation_complete": True,
                "confirmation_rationale": "close still required",
            },
            "layered_state": {"continuation_state": "mature_continuation", "participation": "weak"},
        }
    )
    assert result["entry_confirmation_complete"] is True
    assert result["confirmation_reason"] == "close still required"
    assert result["continuation_state"] == "mature_continuation"
    assert result["participation_state"] == "weak"


def test_tp1_approach_requires_explicit_metadata_for_stopped_trade() -> None:
    signal = {"diagnostics": {"net_tp1_r": 2.0}}
    assert (
        _tp1_approached_before_stop(
            serialized={"outcome": "stop"},
            metadata={"maximum_favorable_excursion_r": 1.7},
            signal=signal,
        )
        is None
    )
    assert (
        _tp1_approached_before_stop(
            serialized={"outcome": "stop"},
            metadata={"tp1_approached_before_stop": True},
            signal=signal,
        )
        is True
    )
    assert (
        _tp1_approached_before_stop(
            serialized={"outcome": "target"},
            metadata={"tp1_approached_before_stop": True},
            signal=signal,
        )
        is None
    )


def test_enriched_diagnostics_calculates_cost_adjusted_tp1_r() -> None:
    result = _enriched_trade_diagnostics(
        signal={
            "entry_price": 100.0,
            "stop_price": 99.0,
            "target_price": 103.0,
            "diagnostics": {
                "entry_atr_distance": 0.5,
                "entry_distance_from_current": 1.0,
                "stop_distance": 1.0,
            },
        },
        metadata={
            "maximum_favorable_excursion_r": 2.25,
            "maximum_adverse_excursion_r": 0.75,
        },
        fee_pct=0.04,
        slippage_pct=0.02,
    )

    assert result["gross_tp1_r"] == 3.0
    assert result["net_tp1_r"] < 3.0
    assert result["maximum_favorable_excursion_r"] == 2.25
    assert "stop_distance_atr" not in result
    assert "stop_distance_atr_source" not in result


def test_r_progress_exposes_fixed_thresholds_and_tp1_ratio() -> None:
    result = _r_progress_diagnostics(
        metadata={"maximum_favorable_excursion_r": 2.4},
        diagnostics={"net_tp1_r": 3.0},
    )

    assert result == {
        "reached_0_5r": True,
        "reached_1r": True,
        "reached_1_5r": True,
        "reached_2r": True,
        "reached_3r": False,
        "tp1_progress_ratio": 0.8,
    }
