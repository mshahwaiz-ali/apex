from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apex.backtesting.contracts import (
    BacktestActivationType,
    BacktestConfig,
    BacktestOutcome,
    BacktestSignal,
)
from apex.backtesting.engine import simulate_trade
from apex.domain.models import Candle
from apex.strategies import StrategyType, TradeDirection

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)


def _candle(
    index: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> Candle:
    opened = NOW + timedelta(minutes=5 * index)
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=opened,
        close_time=opened + timedelta(minutes=5),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1000.0,
        is_closed=True,
        source="test",
    )


def _signal(
    *,
    activation_type: BacktestActivationType = BacktestActivationType.CANDLE_CLOSE,
    activation_level: float = 101.0,
    invalidation: float = 98.0,
    maximum_chase: float = 102.0,
    expiry: int = 3,
) -> BacktestSignal:
    return BacktestSignal(
        symbol="BTCUSDT",
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        direction=TradeDirection.LONG,
        generated_at=NOW,
        entry_price=100.0,
        stop_price=97.0,
        target_price=106.0,
        quantity=1.0,
        risk_amount=3.0,
        confidence_score=80.0,
        activation_type=activation_type,
        activation_level=activation_level,
        pre_entry_invalidation_price=invalidation,
        maximum_chase_price=maximum_chase,
        activation_expiry_candles=expiry,
        candidate_id="candidate-1",
        replay_source="production",
        strategy_version="breakout-v2",
        setup_methodology_version="methodology-v2",
        setup_validity="valid",
        execution_authority="conditional_future",
    )


def test_pre_entry_invalidation_precedes_same_candle_activation() -> None:
    trade = simulate_trade(
        _signal(),
        (
            _candle(
                0,
                open_price=100.0,
                high=101.5,
                low=97.5,
                close=101.2,
            ),
        ),
        config=BacktestConfig(maximum_holding_candles=10),
    )

    assert trade.outcome is BacktestOutcome.PRE_ENTRY_INVALIDATED
    assert trade.metadata["entry_filled"] is False
    assert trade.metadata["terminal_state"] == "pre_entry_invalidated"


def test_close_activation_cannot_fill_until_next_candle() -> None:
    trade = simulate_trade(
        _signal(),
        (
            _candle(0, open_price=100.0, high=101.4, low=99.5, close=101.2),
            _candle(1, open_price=101.2, high=101.4, low=99.8, close=100.2),
            _candle(2, open_price=100.2, high=106.2, low=99.9, close=105.5),
        ),
        config=BacktestConfig(
            fee_pct=0.0,
            slippage_pct=0.0,
            maximum_holding_candles=10,
        ),
    )

    assert trade.outcome is BacktestOutcome.TARGET
    assert trade.metadata["activation_candle"] == 1
    assert trade.metadata["entry_fill_candle"] == 2
    assert trade.metadata["entry_filled"] is True


def test_expiry_before_trigger_is_never_activated() -> None:
    trade = simulate_trade(
        _signal(expiry=2),
        (
            _candle(0, open_price=100.0, high=100.8, low=99.4, close=100.3),
            _candle(1, open_price=100.3, high=100.9, low=99.7, close=100.5),
            _candle(2, open_price=100.5, high=101.5, low=100.0, close=101.2),
        ),
    )

    assert trade.outcome is BacktestOutcome.ACTIVATION_EXPIRED
    assert trade.metadata["entry_filled"] is False
    assert trade.metadata["terminal_state"] == "never_activated"


def test_maximum_chase_precedes_late_trigger() -> None:
    trade = simulate_trade(
        _signal(maximum_chase=101.2),
        (_candle(0, open_price=100.0, high=101.3, low=99.8, close=101.1),),
    )

    assert trade.outcome is BacktestOutcome.MISSED_ENTRY
    assert trade.metadata["entry_filled"] is False
    assert trade.metadata["terminal_state"] == "missed_trigger"


def test_frozen_setup_identity_is_preserved_in_replay_metadata() -> None:
    trade = simulate_trade(
        _signal(expiry=1),
        (_candle(0, open_price=100.0, high=100.8, low=99.4, close=100.3),),
    )

    assert trade.metadata["candidate_id"] == "candidate-1"
    assert trade.metadata["strategy_version"] == "breakout-v2"
    assert trade.metadata["setup_methodology_version"] == "methodology-v2"
    assert trade.metadata["setup_validity"] == "valid"
    assert trade.metadata["execution_authority"] == "conditional_future"


def test_trigger_on_expiry_candle_cannot_activate() -> None:
    trade = simulate_trade(
        _signal(expiry=2),
        (
            _candle(0, open_price=100.0, high=100.8, low=99.4, close=100.3),
            _candle(1, open_price=100.3, high=101.5, low=99.7, close=101.2),
        ),
    )

    assert trade.outcome is BacktestOutcome.ACTIVATION_EXPIRED
    assert trade.metadata["entry_filled"] is False
    assert trade.metadata["activation_outcome"] == "activation_expired"
    assert trade.metadata["terminal_state"] == "never_activated"


def test_pre_entry_invalidation_remains_active_after_close_activation() -> None:
    trade = simulate_trade(
        _signal(),
        (
            _candle(0, open_price=100.0, high=101.4, low=99.5, close=101.2),
            _candle(1, open_price=101.2, high=101.4, low=97.5, close=99.5),
            _candle(2, open_price=99.5, high=106.2, low=99.0, close=105.5),
        ),
    )

    assert trade.outcome is BacktestOutcome.PRE_ENTRY_INVALIDATED
    assert trade.metadata["entry_filled"] is False
    assert trade.metadata["activation_outcome"] == "pre_entry_invalidated_after_activation"
    assert trade.metadata["terminal_state"] == "pre_entry_invalidated"


def test_maximum_chase_remains_active_after_close_activation() -> None:
    trade = simulate_trade(
        _signal(maximum_chase=102.0),
        (
            _candle(0, open_price=100.0, high=101.4, low=99.5, close=101.2),
            _candle(1, open_price=101.2, high=102.4, low=101.1, close=102.2),
            _candle(2, open_price=102.2, high=102.4, low=99.8, close=100.2),
        ),
    )

    assert trade.outcome is BacktestOutcome.MISSED_ENTRY
    assert trade.metadata["entry_filled"] is False
    assert trade.metadata["activation_outcome"] == "maximum_chase_breached_after_activation"
    assert trade.metadata["terminal_state"] == "missed_trigger"


def test_conditional_wait_does_not_consume_post_fill_holding_window() -> None:
    trade = simulate_trade(
        _signal(expiry=5),
        (
            _candle(0, open_price=100.0, high=100.8, low=99.4, close=100.3),
            _candle(1, open_price=100.3, high=101.4, low=99.8, close=101.2),
            _candle(2, open_price=101.2, high=101.4, low=99.8, close=100.2),
            _candle(3, open_price=100.2, high=103.0, low=99.9, close=102.5),
            _candle(4, open_price=102.5, high=106.2, low=102.0, close=105.8),
        ),
        config=BacktestConfig(
            fee_pct=0.0,
            slippage_pct=0.0,
            maximum_holding_candles=3,
        ),
    )

    assert trade.outcome is BacktestOutcome.TARGET
    assert trade.metadata["activation_candle"] == 2
    assert trade.metadata["entry_fill_candle"] == 3
    assert trade.holding_candles == 3


def test_conditional_time_exit_reports_fill_to_exit_holding_duration() -> None:
    trade = simulate_trade(
        _signal(expiry=5),
        (
            _candle(0, open_price=100.0, high=100.8, low=99.4, close=100.3),
            _candle(1, open_price=100.3, high=101.4, low=99.8, close=101.2),
            _candle(2, open_price=101.2, high=101.4, low=99.8, close=100.2),
            _candle(3, open_price=100.2, high=102.5, low=99.9, close=102.0),
            _candle(4, open_price=102.0, high=103.0, low=101.5, close=102.5),
        ),
        config=BacktestConfig(
            fee_pct=0.0,
            slippage_pct=0.0,
            maximum_holding_candles=3,
        ),
    )

    assert trade.outcome is BacktestOutcome.EXPIRED
    assert trade.metadata["entry_fill_candle"] == 3
    assert trade.holding_candles == 3
