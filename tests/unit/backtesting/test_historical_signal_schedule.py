"""Tests for aligned historical signal replay schedules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.backtesting.historical_signal_campaign import (
    HistoricalSignalCampaignInputs,
    HistoricalSourceDataset,
    build_historical_signal_replay_points,
)
from apex.backtesting.historical_signal_replay import (
    HistoricalCandleSeries,
    HistoricalCandleStore,
    HistoricalReplayBoundaries,
    HistoricalSignalSplit,
)
from apex.domain.models import Candle


def _series(
    symbol: str,
    *,
    minute_offset: int = 0,
) -> HistoricalCandleSeries:
    candles: list[Candle] = []
    start = datetime(
        2026,
        6,
        1,
        0,
        0,
        tzinfo=UTC,
    )
    for index in range(6):
        open_time = start + timedelta(minutes=index) + timedelta(minutes=minute_offset)
        candles.append(
            Candle(
                symbol=symbol,
                timeframe="1m",
                open_time=open_time,
                close_time=(open_time + timedelta(minutes=1) - timedelta(milliseconds=1)),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=10.0,
                is_closed=True,
                source="binance",
            )
        )
    return HistoricalCandleSeries(
        symbol=symbol,
        timeframe="1m",
        candles=tuple(candles),
    )


def _inputs(
    *,
    second_symbol_offset: int = 0,
) -> HistoricalSignalCampaignInputs:
    first = _series("BTC/USDT")
    second = _series(
        "ETH/USDT",
        minute_offset=second_symbol_offset,
    )
    boundaries = HistoricalReplayBoundaries(
        analysis_start=datetime(
            2026,
            6,
            1,
            0,
            1,
            tzinfo=UTC,
        ),
        train_end=datetime(
            2026,
            6,
            1,
            0,
            3,
            tzinfo=UTC,
        ),
        validation_end=datetime(
            2026,
            6,
            1,
            0,
            5,
            tzinfo=UTC,
        ),
        analysis_end=datetime(
            2026,
            6,
            1,
            0,
            7,
            tzinfo=UTC,
        ),
    )
    return HistoricalSignalCampaignInputs(
        campaign_id="pilot",
        provider="binance",
        plan_path="plan.json",
        execution_manifest_path="execution.json",
        symbols=("BTC/USDT", "ETH/USDT"),
        timeframes=("1m",),
        boundaries=boundaries,
        store=HistoricalCandleStore((first, second)),
        source_datasets=(
            HistoricalSourceDataset(
                acquisition_order=1,
                symbol="BTC/USDT",
                timeframe="1m",
                dataset_id="btc-1m",
                dataset_path="btc.json",
                content_hash="a" * 64,
                candle_count=6,
            ),
            HistoricalSourceDataset(
                acquisition_order=2,
                symbol="ETH/USDT",
                timeframe="1m",
                dataset_id="eth-1m",
                dataset_path="eth.json",
                content_hash="b" * 64,
                candle_count=6,
            ),
        ),
    )


def test_schedule_uses_closed_finest_timeframe_candles() -> None:
    points = build_historical_signal_replay_points(_inputs())

    assert len(points) == 5
    assert points[0].decision_time == datetime(
        2026,
        6,
        1,
        0,
        1,
        59,
        999000,
        tzinfo=UTC,
    )
    assert points[-1].decision_time == datetime(
        2026,
        6,
        1,
        0,
        5,
        59,
        999000,
        tzinfo=UTC,
    )
    assert tuple(point.split for point in points) == (
        HistoricalSignalSplit.TRAIN,
        HistoricalSignalSplit.TRAIN,
        HistoricalSignalSplit.VALIDATION,
        HistoricalSignalSplit.VALIDATION,
        HistoricalSignalSplit.FINAL_TEST,
    )


def test_schedule_rejects_symbol_timestamp_misalignment() -> None:
    with pytest.raises(
        ValueError,
        match="not aligned across symbols",
    ):
        build_historical_signal_replay_points(_inputs(second_symbol_offset=1))
