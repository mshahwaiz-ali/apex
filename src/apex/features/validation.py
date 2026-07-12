"""Input preparation and active-candle policy for feature calculations."""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from enum import StrEnum

from apex.domain.models import Candle


class ActiveCandlePolicy(StrEnum):
    """How feature calculations treat a final active candle."""

    REJECT = "reject"
    DROP_FINAL = "drop_final"
    ALLOW_FINAL = "allow_final"


def prepare_candles(
    candles: Sequence[Candle],
    *,
    minimum_candles: int,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> tuple[Candle, ...]:
    """Validate and normalize candles before deterministic feature calculation.

    The input order is preserved. Active candles are only valid in the final
    position. The default policy drops that final candle so calculations use
    closed market data and remain stable between repeated evaluations.
    """

    if minimum_candles < 1:
        raise ValueError("minimum_candles must be at least 1")
    if not candles:
        raise ValueError("candle series cannot be empty")

    normalized = tuple(candles)
    first = normalized[0]

    for index, candle in enumerate(normalized):
        if candle.symbol != first.symbol:
            raise ValueError(f"candle {index} symbol does not match the series")
        if candle.timeframe != first.timeframe:
            raise ValueError(f"candle {index} timeframe does not match the series")
        if candle.source != first.source:
            raise ValueError(f"candle {index} source does not match the series")
        if not candle.is_closed and index != len(normalized) - 1:
            raise ValueError("active candle must be the final candle")

    for previous, current in itertools.pairwise(normalized):
        if current.open_time == previous.open_time:
            raise ValueError("candle series contains duplicate timestamps")
        if current.open_time < previous.open_time:
            raise ValueError("candle series must be ordered by open time")

    has_active_final = not normalized[-1].is_closed
    if has_active_final:
        if active_candle_policy is ActiveCandlePolicy.REJECT:
            raise ValueError("active candle is not accepted by this feature")
        if active_candle_policy is ActiveCandlePolicy.DROP_FINAL:
            normalized = normalized[:-1]

    if len(normalized) < minimum_candles:
        raise ValueError(
            f"feature requires at least {minimum_candles} usable candles; "
            f"received {len(normalized)}"
        )

    return normalized
