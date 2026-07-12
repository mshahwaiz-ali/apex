from datetime import UTC, datetime, timedelta

import pytest

from apex.backtesting import (
    BacktestConfig,
    BacktestOutcome,
    BacktestSignal,
    simulate_trade,
    summarize_trades,
)
from apex.domain import Candle
from apex.strategies import StrategyType, TradeDirection

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _signal(*, direction: TradeDirection = TradeDirection.LONG) -> BacktestSignal:
    return BacktestSignal(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=direction,
        generated_at=NOW,
        entry_price=100.0,
        stop_price=98.0 if direction is TradeDirection.LONG else 102.0,
        target_price=104.0 if direction is TradeDirection.LONG else 96.0,
        quantity=10.0,
        risk_amount=20.0,
        confidence_score=80.0,
    )


def _candle(
    *,
    high: float,
    low: float,
    close: float = 100.0,
    open_price: float = 100.0,
    index: int = 0,
) -> Candle:
    return Candle(
        symbol="BTC/USDT",
        timeframe="5m",
        open_time=NOW + timedelta(minutes=5 * index),
        close_time=NOW + timedelta(minutes=5 * (index + 1)),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        is_closed=True,
        source="fixture",
    )


def test_conservative_intrabar_ambiguity_uses_stop_first() -> None:
    trade = simulate_trade(
        _signal(),
        (_candle(high=105.0, low=97.0),),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    assert trade.outcome is BacktestOutcome.STOP
    assert trade.net_pnl == pytest.approx(-20.0)
    assert trade.realized_r_multiple == pytest.approx(-1.0)


def test_non_conservative_intrabar_can_use_target_first() -> None:
    trade = simulate_trade(
        _signal(),
        (_candle(high=105.0, low=97.0),),
        config=BacktestConfig(
            fee_pct=0.0,
            slippage_pct=0.0,
            conservative_intrabar=False,
        ),
    )

    assert trade.outcome is BacktestOutcome.TARGET
    assert trade.net_pnl == pytest.approx(40.0)


def test_short_trade_target_and_summary_metrics() -> None:
    trade = simulate_trade(
        _signal(direction=TradeDirection.SHORT),
        (_candle(high=101.0, low=95.0),),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )
    report = summarize_trades((trade,))

    assert trade.outcome is BacktestOutcome.TARGET
    assert trade.net_pnl == pytest.approx(40.0)
    assert report.total_trades == 1
    assert report.win_rate == pytest.approx(1.0)
    assert report.by_symbol == {"BTC/USDT": 1}
    assert report.by_strategy == {"trend_pullback": 1}


def test_unentered_trade_expires_at_last_allowed_candle() -> None:
    trade = simulate_trade(
        _signal(),
        (
            _candle(high=99.0, low=98.5, close=99.0, open_price=99.0, index=0),
            _candle(high=99.5, low=98.5, close=99.2, open_price=99.0, index=1),
        ),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0, maximum_holding_candles=2),
    )

    assert trade.outcome is BacktestOutcome.EXPIRED
    assert trade.holding_candles == 2
