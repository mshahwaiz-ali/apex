"""Normalized optional futures-participation evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from apex.domain.models import ExchangeFilterSnapshot, OrderBookSnapshot, TickerSnapshot


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


@dataclass(frozen=True, slots=True)
class PremiumIndexSnapshot:
    """Current mark/index relationship reported by the futures venue."""

    symbol: str
    mark_price: float
    index_price: float
    last_funding_rate: float | None
    next_funding_time: datetime | None
    captured_at: datetime
    source: str

    def __post_init__(self) -> None:
        _validate(self.symbol, self.captured_at, self.source)
        if self.mark_price <= 0 or self.index_price <= 0:
            raise ValueError("mark and index prices must be positive")
        if self.last_funding_rate is not None and not math.isfinite(self.last_funding_rate):
            raise ValueError("last funding rate must be finite")
        if self.next_funding_time is not None and (
            self.next_funding_time.tzinfo is None or self.next_funding_time.utcoffset() is None
        ):
            raise ValueError("next funding timestamp must be timezone-aware")

    @property
    def basis_percentage(self) -> float:
        return (self.mark_price - self.index_price) / self.index_price * 100


@dataclass(frozen=True, slots=True)
class MarketEvidenceBundle:
    """Timestamped derivatives evidence; missing inputs stay explicit, never zero-filled."""

    symbol: str
    as_of: datetime
    funding: tuple[FundingRateSnapshot, ...] = ()
    open_interest: tuple[OpenInterestSnapshot, ...] = ()
    taker_flow: tuple[TakerFlowSnapshot, ...] = ()
    premium_index: PremiumIndexSnapshot | None = None
    ticker: TickerSnapshot | None = None
    order_book: OrderBookSnapshot | None = None
    exchange_filters: ExchangeFilterSnapshot | None = None
    missing_reasons: tuple[tuple[str, str], ...] = ()
    source: str = "binance-futures"

    def __post_init__(self) -> None:
        _validate(self.symbol, self.as_of, self.source)

    @property
    def available_inputs(self) -> tuple[str, ...]:
        inputs: list[str] = []
        if self.funding:
            inputs.append("funding")
        if self.open_interest:
            inputs.append("open_interest")
        if self.taker_flow:
            inputs.append("taker_flow")
        if self.premium_index is not None:
            inputs.append("premium_index")
        return tuple(inputs)

    @property
    def execution_inputs(self) -> tuple[str, ...]:
        inputs: list[str] = []
        if self.ticker is not None:
            inputs.append("ticker")
        if self.order_book is not None:
            inputs.append("order_book")
        if self.exchange_filters is not None:
            inputs.append("exchange_filters")
        return tuple(inputs)


__all__ = [
    "FundingRateSnapshot",
    "MarketEvidenceBundle",
    "OpenInterestSnapshot",
    "PremiumIndexSnapshot",
    "TakerFlowSnapshot",
]
