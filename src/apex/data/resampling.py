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
    if limit is not None and limit <