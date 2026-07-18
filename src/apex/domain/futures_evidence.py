"""Normalized optional futures-participation evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


def _validate(symbol: str, captured_at: datetime, source: str) -> None:
    if not symbol.strip() or not source.strip():
        raise ValueError("futures evidence symbol and source cannot be empty")
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("futures evidence timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True)
class FundingRateSnapshot:
    symbol: str
    funding_rate: float
    funding_time: datetime
    source: str

    def __post_init__(self) -> None:
        _validate(self.symbol, self.funding_time, self.source)
        if not math.isfinite(self.funding_rate):
            raise ValueError("funding rate must be finite")


@dataclass(frozen=True, slots=True)
class OpenInterestSnapshot:
    symbol: str
    period: str
    open_interest: float
    open_interest_value: float
    captured_at: datetime
    source: str

    def __post_init__(self) -> None:
        _validate(self.symbol, self.captured_at, self.source)
        if not self.period.strip():
            raise ValueError("open-interest period cannot be empty")
        if self.open_interest < 0 or self.open_interest_value < 0:
            raise ValueError("open interest cannot be negative")


@dataclass(frozen=True, slots=True)
class TakerFlowSnapshot:
    symbol: str
    period: str
    buy_volume: float
    sell_volume: float
    buy_sell_ratio: float
    captured_at: datetime
    source: str

    def __post_init__(self) -> None:
        _validate(self.symbol, self.captured_at, self.source)
        if not self.period.strip():
            raise ValueError("taker-flow period cannot be empty")
        if self.buy_volume < 0 or self.sell_volume < 0 or self.buy_sell_ratio < 0:
            raise ValueError("taker-flow values cannot be negative")


__all__ = ["FundingRateSnapshot", "OpenInterestSnapshot", "TakerFlowSnapshot"]
