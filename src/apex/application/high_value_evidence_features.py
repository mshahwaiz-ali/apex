"""Central, fail-closed derivation of high-value participation evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from apex.domain.futures_evidence import OpenInterestSnapshot, TakerFlowSnapshot
    from apex.domain.models import Candle


class ChangeDirection(StrEnum):
    RISING = "rising"
    FALLING = "falling"
    FLAT = "flat"


class PriceOpenInterestState(StrEnum):
    LONG_BUILDUP = "long_buildup"
    SHORT_BUILDUP = "short_buildup"
    SHORT_COVERING = "short_covering"
    LONG_UNWINDING = "long_unwinding"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class TakerFlowImbalanceProxy:
    """Fresh taker buy/sell history summarized without calling it aggregate trades."""

    buy_volume: float
    sell_volume: float
    imbalance: float
    sample_count: int
    latest_captured_at: datetime
    source_label: str = "taker_flow_history_proxy"

    def __post_init__(self) -> None:
        for name, value in (
            ("buy volume", self.buy_volume),
            ("sell volume", self.sell_volume),
            ("imbalance", self.imbalance),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.buy_volume < 0.0 or self.sell_volume < 0.0:
            raise ValueError("taker-flow volumes cannot be negative")
        if not -1.0 <= self.imbalance <= 1.0:
            raise ValueError("taker-flow imbalance must be between -1 and 1")
        if self.sample_count <= 0:
            raise ValueError("taker-flow proxy requires at least one sample")
        if self.latest_captured_at.tzinfo is None or self.latest_captured_at.utcoffset() is None:
            raise ValueError("taker-flow proxy timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True)
class PriceOpenInterestRelationship:
    """Price and open-interest changes derived from timestamp-aligned observations."""

    price_change_pct: float
    open_interest_change_pct: float
    price_direction: ChangeDirection
    open_interest_direction: ChangeDirection
    state: PriceOpenInterestState
    start_at: datetime
    end_at: datetime
    maximum_alignment_skew_seconds: float
    source_labels: tuple[str, str] = ("closed_candles", "open_interest_history")

    def __post_init__(self) -> None:
        for name, value in (
            ("price change percentage", self.price_change_pct),
            ("open-interest change percentage", self.open_interest_change_pct),
            ("maximum alignment skew", self.maximum_alignment_skew_seconds),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.maximum_alignment_skew_seconds < 0.0:
            raise ValueError("maximum alignment skew cannot be negative")
        if self.start_at.tzinfo is None or self.start_at.utcoffset() is None:
            raise ValueError("relationship start timestamp must be timezone-aware")
        if self.end_at.tzinfo is None or self.end_at.utcoffset() is None:
            raise ValueError("relationship end timestamp must be timezone-aware")
        if self.end_at <= self.start_at:
            raise ValueError("relationship end timestamp must follow start timestamp")


def derive_taker_flow_imbalance_proxy(
    values: Sequence[TakerFlowSnapshot],
    *,
    as_of: datetime,
    max_age: timedelta = timedelta(minutes=30),
) -> TakerFlowImbalanceProxy | None:
    """Return a fresh cumulative taker-flow proxy, or ``None`` fail-closed."""

    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    if max_age <= timedelta(0):
        raise ValueError("max_age must be positive")
    if not values:
        return None

    ordered = tuple(sorted(values, key=lambda item: item.captured_at))
    latest = ordered[-1]
    age = as_of - latest.captured_at
    if age < timedelta(0) or age > max_age:
        return None

    buy_volume = sum(item.buy_volume for item in ordered)
    sell_volume = sum(item.sell_volume for item in ordered)
    total = buy_volume + sell_volume
    if total <= 0.0:
        return None
    imbalance = (buy_volume - sell_volume) / total
    return TakerFlowImbalanceProxy(
        buy_volume=buy_volume,
        sell_volume=sell_volume,
        imbalance=imbalance,
        sample_count=len(ordered),
        latest_captured_at=latest.captured_at,
    )


def derive_price_open_interest_relationship(
    candles: Sequence[Candle],
    open_interest: Sequence[OpenInterestSnapshot],
    *,
    as_of: datetime,
    max_age: timedelta = timedelta(minutes=30),
    max_alignment_skew: timedelta = timedelta(minutes=6),
    flat_change_pct: float = 0.05,
) -> PriceOpenInterestRelationship | None:
    """Derive aligned price/OI change; reject stale, sparse, or unsynchronized inputs."""

    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    if max_age <= timedelta(0) or max_alignment_skew < timedelta(0):
        raise ValueError("age and alignment bounds must be valid")
    if flat_change_pct < 0.0 or not math.isfinite(flat_change_pct):
        raise ValueError("flat change threshold must be finite and non-negative")

    closed = tuple(
        sorted((item for item in candles if item.is_closed), key=lambda item: item.close_time)
    )
    oi = tuple(sorted(open_interest, key=lambda item: item.captured_at))
    if len(closed) < 2 or len(oi) < 2:
        return None
    if as_of - closed[-1].close_time > max_age or as_of - oi[-1].captured_at > max_age:
        return None
    if closed[-1].close_time > as_of or oi[-1].captured_at > as_of:
        return None

    start_pair = _nearest_pair(closed, oi[0].captured_at, max_alignment_skew)
    end_pair = _nearest_pair(closed, oi[-1].captured_at, max_alignment_skew)
    if start_pair is None or end_pair is None:
        return None

    start_candle, start_skew = start_pair
    end_candle, end_skew = end_pair
    if end_candle.close_time <= start_candle.close_time:
        return None
    start_oi = oi[0].open_interest
    end_oi = oi[-1].open_interest
    if start_oi <= 0.0:
        return None

    price_change_pct = (end_candle.close - start_candle.close) / start_candle.close * 100.0
    oi_change_pct = (end_oi - start_oi) / start_oi * 100.0
    price_direction = _direction(price_change_pct, flat_change_pct)
    oi_direction = _direction(oi_change_pct, flat_change_pct)

    return PriceOpenInterestRelationship(
        price_change_pct=price_change_pct,
        open_interest_change_pct=oi_change_pct,
        price_direction=price_direction,
        open_interest_direction=oi_direction,
        state=_relationship_state(price_direction, oi_direction),
        start_at=start_candle.close_time,
        end_at=end_candle.close_time,
        maximum_alignment_skew_seconds=max(start_skew, end_skew),
    )


def _nearest_pair(
    candles: Sequence[Candle],
    timestamp: datetime,
    maximum_skew: timedelta,
) -> tuple[Candle, float] | None:
    nearest = min(
        candles,
        key=lambda item: abs((item.close_time - timestamp).total_seconds()),
    )
    skew_seconds = abs((nearest.close_time - timestamp).total_seconds())
    if skew_seconds > maximum_skew.total_seconds():
        return None
    return nearest, skew_seconds


def _direction(change_pct: float, flat_change_pct: float) -> ChangeDirection:
    if change_pct > flat_change_pct:
        return ChangeDirection.RISING
    if change_pct < -flat_change_pct:
        return ChangeDirection.FALLING
    return ChangeDirection.FLAT


def _relationship_state(
    price: ChangeDirection,
    open_interest: ChangeDirection,
) -> PriceOpenInterestState:
    if price is ChangeDirection.RISING and open_interest is ChangeDirection.RISING:
        return PriceOpenInterestState.LONG_BUILDUP
    if price is ChangeDirection.FALLING and open_interest is ChangeDirection.RISING:
        return PriceOpenInterestState.SHORT_BUILDUP
    if price is ChangeDirection.RISING and open_interest is ChangeDirection.FALLING:
        return PriceOpenInterestState.SHORT_COVERING
    if price is ChangeDirection.FALLING and open_interest is ChangeDirection.FALLING:
        return PriceOpenInterestState.LONG_UNWINDING
    return PriceOpenInterestState.INDETERMINATE


__all__ = [
    "ChangeDirection",
    "PriceOpenInterestRelationship",
    "PriceOpenInterestState",
    "TakerFlowImbalanceProxy",
    "derive_price_open_interest_relationship",
    "derive_taker_flow_imbalance_proxy",
]
