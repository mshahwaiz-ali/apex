from datetime import UTC, datetime, timedelta

from apex.application.chronological_metadata import (
    ChronologicalBacktestMetadata,
    build_chronological_metadata,
)
from apex.backtesting import BacktestConfig
from apex.domain import Candle
from apex.risk import DEFAULT_RISK_CONFIG

START = datetime(2026, 1, 1, tzinfo=UTC)


def _candle(index: int, *, timeframe: str = "5m", closed: bool = True) -> Candle:
    open_time = START + timedelta(minutes=5 * index)
    return Candle(
        symbol="BTC/USDT",
        timeframe=timeframe,
        open_time=open_time,
        close_time=open_time + timedelta(minutes=5),
        open=100.0 + index,
        high=101.0 + index,
        low=99.0 + index,
        close=100.5 + index,
        volume=1000.0 + index,
        is_closed=closed,
        source="fixture",
    )


def _metadata(
    candles: tuple[Candle, ...],
    *,
    cooldown: int = 3,
) -> ChronologicalBacktestMetadata:
    return build_chronological_metadata(
        symbol="BTC/USDT",
        candles_by_timeframe={"5m": candles},
        analysis_timeframes=("5m",),
        replay_timeframe="5m",
        candle_limit=40,
        decision_interval_candles=2,
        candidate_cooldown_candles=cooldown,
        risk_config=DEFAULT_RISK_CONFIG,
        backtest_config=BacktestConfig(),
        generated_at=START,
    )


def test_metadata_hashes_are_deterministic_and_ignore_active_candles() -> None:
    closed = tuple(_candle(index) for index in range(3))
    first = _metadata((*closed, _candle(3, closed=False)))
    second = _metadata(closed)

    assert first.dataset_hash == second.dataset_hash
    assert first.config_hash == second.config_hash
    assert first.closed_candle_counts == {"5m": 3}
    assert first.first_candle_at == closed[0].open_time
    assert first.last_candle_at == closed[-1].close_time


def test_config_hash_changes_when_replay_controls_change() -> None:
    candles = tuple(_candle(index) for index in range(3))

    assert (
        _metadata(candles, cooldown=3).dataset_hash == _metadata(candles, cooldown=5).dataset_hash
    )
    assert _metadata(candles, cooldown=3).config_hash != _metadata(candles, cooldown=5).config_hash


def test_dataset_hash_changes_when_closed_candle_data_changes() -> None:
    candles = tuple(_candle(index) for index in range(3))
    changed = (*candles[:-1], _candle(4))

    assert _metadata(candles).dataset_hash != _metadata(changed).dataset_hash
