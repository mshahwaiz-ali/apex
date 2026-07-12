"""Validation for normalized candle series."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from apex.data.timeframes import TIMEFRAME_DELTAS
from apex.domain.models import Candle


@dataclass(frozen=True)
class CandleSeriesValidationResult:
    """Result of validating a normalized candle sequence."""

    is_valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def validate_candle_series(
    candles: list[Candle],
    *,
    expected_timeframe: str,
    now: datetime,
    max_staleness_intervals: int | None = 2,
) -> CandleSeriesValidationResult:
    """Validate ordering, continuity, consistency, and freshness."""

    errors: list[str] = []
    warnings: list[str] = []

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("validation clock must be timezone-aware")

    if not candles:
        return CandleSeriesValidationResult(
            is_valid=False,
            errors=("candle series is empty",),
            warnings=(),
        )

    interval = TIMEFRAME_DELTAS.get(expected_timeframe)
    if interval is None:
        return CandleSeriesValidationResult(
            is_valid=False,
            errors=(f"unsupported timeframe: {expected_timeframe}",),
            warnings=(),
        )

    seen_open_times: set[datetime] = set()

    for index, candle in enumerate(candles):
        if candle.open_time.tzinfo is None or candle.open_time.utcoffset() is None:
            errors.append(f"candle {index} open_time must be timezone-aware")
        if candle.close_time.tzinfo is None or candle.close_time.utcoffset() is None:
            errors.append(f"candle {index} close_time must be timezone-aware")
        if candle.open_time > now:
            errors.append(f"candle {index} open_time is in the future")
        if candle.is_closed and candle.close_time > now:
            errors.append(f"candle {index} is marked closed before close_time")
        if not candle.is_closed and candle.close_time <= now:
            errors.append(f"candle {index} is marked active after close_time")
        if candle.timeframe != expected_timeframe:
            errors.append(
                f"candle {index} timeframe mismatch: {candle.timeframe} != {expected_timeframe}"
            )

        if candle.open_time in seen_open_times:
            errors.append(f"duplicate candle open_time at index {index}")

        seen_open_times.add(candle.open_time)

        if index == 0:
            continue

        previous = candles[index - 1]

        if candle.open_time <= previous.open_time:
            errors.append(f"candles are not strictly ordered at index {index}")
            continue

        actual_gap = candle.open_time - previous.open_time

        if actual_gap != interval:
            errors.append(
                f"unexpected candle interval at index {index}: {actual_gap} != {interval}"
            )

    active_candles = [candle for candle in candles if not candle.is_closed]

    if len(active_candles) > 1:
        errors.append("more than one active candle found")

    if active_candles and candles[-1].is_closed:
        errors.append("active candle must be the final candle")

    latest_closed = next(
        (candle for candle in reversed(candles) if candle.is_closed),
        None,
    )

    if latest_closed is None:
        warnings.append("series contains no closed candles")
    elif max_staleness_intervals is not None:
        if max_staleness_intervals < 0:
            raise ValueError("max_staleness_intervals cannot be negative")

        staleness_limit = interval * max_staleness_intervals
        if now - latest_closed.close_time > staleness_limit:
            errors.append("latest closed candle is stale")

    return CandleSeriesValidationResult(
        is_valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
