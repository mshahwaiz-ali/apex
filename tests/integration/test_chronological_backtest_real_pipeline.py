from datetime import UTC, datetime, timedelta

from apex.application.chronological_backtest import (
    ChronologicalBacktestRequest,
    run_chronological_pipeline_backtest,
)
from apex.domain import Candle

START = datetime(2026, 1, 1, tzinfo=UTC)


def _candles(count: int) -> tuple[Candle, ...]:
    candles: list[Candle] = []
    price = 100.0
    for index in range(count):
        drift = 0.15 if index % 8 < 6 else -0.05
        open_price = price
        close_price = max(1.0, open_price + drift)
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="5m",
                open_time=START + timedelta(minutes=5 * index),
                close_time=START + timedelta(minutes=5 * (index + 1)),
                open=open_price,
                high=max(open_price, close_price) + 0.25,
                low=min(open_price, close_price) - 0.25,
                close=close_price,
                volume=100.0 + index,
                is_closed=True,
                source="fixture",
            )
        )
        price = close_price
    return tuple(candles)


def test_chronological_runner_executes_real_analysis_pipeline_without_ticker_failures() -> None:
    result = run_chronological_pipeline_backtest(
        ChronologicalBacktestRequest(
            symbol="BTC/USDT",
            candles_by_timeframe={"5m": _candles(45)},
            analysis_timeframes=("5m",),
            replay_timeframe="5m",
            candle_limit=40,
        )
    )

    assert result.decision_count == 5
    assert result.failure_count == 0
    assert result.failures == {}
    assert result.approved_count + result.skipped_count == result.decision_count
