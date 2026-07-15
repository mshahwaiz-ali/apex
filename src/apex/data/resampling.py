"""Deterministic OHLCV candle resampling."""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from apex.data.timeframes import timeframe_delta
from apex.domain.models import Candle


def resample_candles(
    candles: Iterable[Candle],
    *,
    target_timeframe: str,
    source_timeframe: str,
    limit: int | None = None,
) -> list[Candle]:
    """Resample lower-timeframe candles into a higher timeframe without lookahead."""

    source = tuple(candles)
    if not source:
        return []
    if limit is not None and limit < 1:
        raise ValueError("resample limit must be at least one when provided")

    source_delta = timeframe_delta(source_timeframe)
    target_delta = timeframe_delta(target_timeframe)
    if target_delta <= source_delta:
        raise ValueError("target timeframe must be higher than source timeframe")

    _validate_source_candles(source, source_timeframe=source_timeframe, interval=source_delta)

    resampled: list[Candle] = []
    for bucket_start, bucket_candles_iter in itertools.groupby(
        source,
        key=lambda candle: _bucket_start(candle.open_time, target_delta),
    ):
        bucket = tuple(bucket_candles_iter)
        if not bucket:
            continue

        bucket_end = bucket_start + target_delta
        starts_at_bucket_boundary = bucket[0].open_time == bucket_start
        reaches_bucket_end = bucket[-1].open_time + source_delta >= bucket_end
        is_complete = (
            starts_at_bucket_boundary
            and reaches_bucket_end
            and all(candle.is_closed for candle in bucket)
        )

        if not starts_at_bucket_boundary and not resampled:
            continue

        if not is_complete and bucket[-1] is not source[-1]:
            raise ValueError("incomplete resampled candle before final bucket")

        resampled.append(
            Candle(
                symbol=bucket[0].symbol,
                timeframe=target_timeframe,
                open_time=bucket_start,
                close_time=bucket_end,
                open=bucket[0].open,
                high=max(candle.high for candle in bucket),
                low=min(candle.low for candle in bucket),
                close=bucket[-1].close,
                volume=sum(candle.volume for candle in bucket),
                is_closed=is_complete,
                source=f"resampled:{source_timeframe}:{bucket[0].source}",
            )
        )

    if limit is not None:
        return resampled[-limit:]
    return resampled


def source_limit_for_resampling(
    *,
    target_timeframe: str,
    source_timeframe: str,
    target_limit: int,
    max_source_limit: int,
) -> int:
    """Return a bounded source candle request size for a target resampling request."""

    if target_limit < 1:
        raise ValueError("target limit must be at least one")
    if max_source_limit < 1:
        raise ValueError("max source limit must be at least one")

    source_delta = timeframe_delta(source_timeframe)
    target_delta = timeframe_delta(target_timeframe)
    if target_delta <= source_delta:
        raise ValueError("target timeframe must be higher than source timeframe")

    ratio = int(target_delta / source_delta)
    requested = target_limit * ratio + ratio
    return min(requested, max_source_limit)


def _validate_source_candles(
    candles: tuple[Candle, ...],
    *,
    source_timeframe: str,
    interval: timedelta,
) -> None:
    symbols = {candle.symbol for candle in candles}
    sources = {candle.source for candle in candles}
    if len(symbols) != 1:
        raise ValueError("source candles must have one symbol")
    if len(sources) != 1:
        raise ValueError("source candles must have one source")

    active_indexes = [index for index, candle in enumerate(candles) if not candle.is_closed]
    if len(active_indexes) > 1:
        raise ValueError("source candles cannot contain multiple active candles")
    if active_indexes and active_indexes[0] != len(candles) - 1:
        raise ValueError("source active candle must be final")

    for index, candle in enumerate(candles):
        if candle.timeframe != source_timeframe:
            raise ValueError(f"source candle {index} timeframe mismatch")

    for previous, current in itertools.pairwise(candles):
        if current.open_time <= previous.open_time:
            raise ValueError("source candles must be strictly ordered")
        if current.open_time - previous.open_time != interval:
            raise ValueError("source candles contain an interval gap")


def _bucket_start(value: datetime, interval: timedelta) -> datetime:
    timestamp = value.astimezone(UTC).timestamp()
    seconds = int(interval.total_seconds())
    bucket_timestamp = int(timestamp // seconds) * seconds
    return datetime.fromtimestamp(bucket_timestamp, tz=UTC)
