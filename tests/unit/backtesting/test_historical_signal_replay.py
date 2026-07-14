"""Tests for leak-proof historical signal replay primitives."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.backtesting.historical_signal_replay import (
    HistoricalCandleSeries,
    HistoricalCandleStore,
    HistoricalReplayBoundaries,
    HistoricalReplayProvider,
    HistoricalSignalSplit,
    build_replay_points,
)
from apex.domain.models import Candle


def _candle(index: int, *, timeframe: str = "1m") -> Candle:
    open_time = datetime(2026, 6, 1, tzinfo=UTC) + timedelta(minutes=index)
    return Candle(
        symbol="BTC/USDT",
        timeframe=timeframe,
        open_time=open_time,
        close_time=open_time + timedelta(minutes=1) - timedelta(milliseconds=1),
        open=100.0 + index,
        high=101.0 + index,
        low=99.0 + index,
        close=100.5 + index,
        volume=10.0 + index,
        is_closed=True,
        source="fixture",
    )


def _store() -> HistoricalCandleStore:
    return HistoricalCandleStore(
        (
            HistoricalCandleSeries(
                symbol="BTC/USDT",
                timeframe="1m",
                candles=tuple(_candle(index) for index in range(6)),
            ),
        )
    )


def _boundaries() -> HistoricalReplayBoundaries:
    return HistoricalReplayBoundaries(
        analysis_start=datetime(2026, 6, 1, 0, 1, tzinfo=UTC),
        train_end=datetime(2026, 6, 1, 0, 3, tzinfo=UTC),
        validation_end=datetime(2026, 6, 1, 0, 5, tzinfo=UTC),
        analysis_end=datetime(2026, 6, 1, 0, 7, tzinfo=UTC),
    )


def test_provider_exposes_only_candles_closed_by_decision_time() -> None:
    provider = HistoricalReplayProvider(
        store=_store(),
        decision_time=datetime(2026, 6, 1, 0, 3, tzinfo=UTC),
    )

    candles = provider.fetch_candles("BTC/USDT", "1m", limit=20)

    assert [candle.open_time.minute for candle in candles] == [0, 1, 2]
    assert all(candle.close_time <= provider.decision_time for candle in candles)


def test_provider_never_exposes_future_candle_even_with_large_limit() -> None:
    provider = HistoricalReplayProvider(
        store=_store(),
        decision_time=datetime(
            2026,
            6,
            1,
            0,
            2,
            30,
            tzinfo=UTC,
        ),
    )

    candles = provider.fetch_candles("BTC/USDT", "1m", limit=10_000)

    assert [candle.open_time.minute for candle in candles] == [0, 1]
    assert all(candle.open_time.minute < 2 for candle in candles)


def test_provider_applies_requested_window_limit() -> None:
    provider = HistoricalReplayProvider(
        store=_store(),
        decision_time=datetime(2026, 6, 1, 0, 6, tzinfo=UTC),
    )

    candles = provider.fetch_candles("BTC/USDT", "1m", limit=2)

    assert [candle.open_time.minute for candle in candles] == [4, 5]


def test_replay_points_are_chronological_and_split_at_exact_boundaries() -> None:
    points = build_replay_points(
        decision_times=(
            datetime(2026, 6, 1, 0, 1, tzinfo=UTC),
            datetime(2026, 6, 1, 0, 3, tzinfo=UTC),
            datetime(2026, 6, 1, 0, 5, tzinfo=UTC),
            datetime(2026, 6, 1, 0, 6, tzinfo=UTC),
        ),
        boundaries=_boundaries(),
    )

    assert tuple(point.split for point in points) == (
        HistoricalSignalSplit.TRAIN,
        HistoricalSignalSplit.VALIDATION,
        HistoricalSignalSplit.FINAL_TEST,
        HistoricalSignalSplit.FINAL_TEST,
    )
    assert tuple(point.decision_time for point in points) == tuple(
        sorted(point.decision_time for point in points)
    )


def test_replay_point_generation_is_deterministic() -> None:
    decision_times = (
        datetime(2026, 6, 1, 0, 1, tzinfo=UTC),
        datetime(2026, 6, 1, 0, 2, tzinfo=UTC),
        datetime(2026, 6, 1, 0, 3, tzinfo=UTC),
    )

    first = build_replay_points(
        decision_times=decision_times,
        boundaries=_boundaries(),
    )
    second = build_replay_points(
        decision_times=decision_times,
        boundaries=_boundaries(),
    )

    assert first == second


def test_replay_rejects_duplicate_or_out_of_order_timestamps() -> None:
    timestamp = datetime(2026, 6, 1, 0, 2, tzinfo=UTC)

    with pytest.raises(
        ValueError,
        match="strictly increasing",
    ):
        build_replay_points(
            decision_times=(timestamp, timestamp),
            boundaries=_boundaries(),
        )


def test_replay_rejects_timestamp_outside_analysis_range() -> None:
    with pytest.raises(
        ValueError,
        match="inside the campaign analysis range",
    ):
        build_replay_points(
            decision_times=(datetime(2026, 6, 1, 0, 0, tzinfo=UTC),),
            boundaries=_boundaries(),
        )


def test_store_rejects_non_closed_source_candles() -> None:
    candle = _candle(0).model_copy(update={"is_closed": False})

    with pytest.raises(
        ValueError,
        match="requires closed source candles",
    ):
        HistoricalCandleSeries(
            symbol="BTC/USDT",
            timeframe="1m",
            candles=(candle,),
        )


def test_store_rejects_duplicate_series() -> None:
    series = HistoricalCandleSeries(
        symbol="BTC/USDT",
        timeframe="1m",
        candles=(_candle(0),),
    )

    with pytest.raises(
        ValueError,
        match="duplicate series",
    ):
        HistoricalCandleStore((series, series))


def test_historical_ticker_is_explicitly_unavailable() -> None:
    provider = HistoricalReplayProvider(
        store=_store(),
        decision_time=datetime(2026, 6, 1, 0, 3, tzinfo=UTC),
    )

    with pytest.raises(
        LookupError,
        match="ticker snapshot is unavailable",
    ):
        provider.fetch_ticker("BTC/USDT")
