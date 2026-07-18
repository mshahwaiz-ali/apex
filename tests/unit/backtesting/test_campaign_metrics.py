from datetime import UTC, datetime, timedelta

import pytest

from apex.backtesting import BacktestConfig, BacktestSignal, simulate_trade, summarize_trades
from apex.cli_commands.backtesting import _jsonable, _report_metrics
from apex.domain.models import Candle
from apex.strategies import StrategyType, TradeDirection


def _signal() -> BacktestSignal:
    return BacktestSignal(
        symbol="BTCUSDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        quantity=1.0,
        risk_amount=2.0,
        confidence_score=70.0,
    )


def _candle(index: int, *, low: float, high: float, close: float) -> Candle:
    opened = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=5 * index)
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=opened,
        close_time=opened + timedelta(minutes=5),
        open=close,
        high=high,
        low=low,
        close=close,
        volume=1_000.0,
        is_closed=True,
        source="test",
    )


def test_trade_records_excursions_and_funding_drag() -> None:
    trade = simulate_trade(
        _signal(),
        (
            _candle(1, low=99.0, high=102.0, close=101.0),
            _candle(2, low=100.0, high=104.5, close=104.0),
        ),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0, funding_pct=0.1),
    )

    assert trade.metadata["maximum_favorable_excursion_r"] == pytest.approx(2.25)
    assert trade.metadata["maximum_adverse_excursion_r"] == pytest.approx(0.5)
    assert trade.metadata["actual_funding"] == pytest.approx(0.1)
    assert trade.net_pnl == pytest.approx(3.9)


def test_campaign_report_exposes_fill_and_excursion_metrics() -> None:
    filled = simulate_trade(
        _signal(),
        (_candle(1, low=99.0, high=104.5, close=104.0),),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )
    missed = simulate_trade(
        _signal(),
        (_candle(1, low=105.0, high=106.0, close=105.5),),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    report = summarize_trades((filled, missed))

    assert report.metadata["entry_fill_rate"] == pytest.approx(0.5)
    assert report.metadata["tp1_touch_count"] == 1
    assert report.metadata["average_mfe_r"] > 0

    serialized_trade = _jsonable(filled)
    metrics = _report_metrics(report)
    assert isinstance(serialized_trade, dict)
    assert serialized_trade["metadata"]["maximum_favorable_excursion_r"] > 0
    assert metrics["trades"] == []
    assert metrics["metadata"]["entry_fill_rate"] == pytest.approx(0.5)
