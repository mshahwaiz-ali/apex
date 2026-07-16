"""Typed contracts for lightweight futures-market screening."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.domain.futures_market import FuturesContractMetadata


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty")


@dataclass(frozen=True, slots=True)
class FuturesTickerSnapshot:
    """One normalized market-wide futures ticker record."""

    symbol: str
    exchange_symbol: str
    last_price: float
    bid_price: float
    ask_price: float
    quote_volume_24h: float
    price_change_percentage_24h: float
    captured_at: datetime
    source: str
    high_price_24h: float | None = None
    low_price_24h: float | None = None
    trade_count_24h: int | None = None

    def __post_init__(self) -> None:
        for field_name, value in {
            "symbol": self.symbol,
            "exchange_symbol": self.exchange_symbol,
            "source": self.source,
        }.items():
            _require_text(field_name, value)

        if self.last_price <= 0:
            raise ValueError("last_price must be positive")
        if self.bid_price <= 0:
            raise ValueError("bid_price must be positive")
        if self.ask_price <= 0:
            raise ValueError("ask_price must be positive")
        if self.bid_price > self.ask_price:
            raise ValueError("bid_price cannot exceed ask_price")
        if self.quote_volume_24h < 0:
            raise ValueError("quote_volume_24h cannot be negative")

        if self.high_price_24h is not None and self.high_price_24h <= 0:
            raise ValueError("high_price_24h must be positive when provided")
        if self.low_price_24h is not None and self.low_price_24h <= 0:
            raise ValueError("low_price_24h must be positive when provided")

        if (
            self.high_price_24h is not None
            and self.low_price_24h is not None
            and self.low_price_24h > self.high_price_24h
        ):
            raise ValueError("low_price_24h cannot exceed high_price_24h")

        if self.trade_count_24h is not None and self.trade_count_24h < 0:
            raise ValueError("trade_count_24h cannot be negative")

    @property
    def spread(self) -> float:
        """Return the absolute best-bid/best-ask spread."""

        return self.ask_price - self.bid_price

    @property
    def spread_percentage(self) -> float:
        """Return spread as a percentage of the bid/ask midpoint."""

        midpoint = (self.bid_price + self.ask_price) / 2
        return self.spread / midpoint * 100

    @property
    def absolute_movement_percentage(self) -> float:
        """Return the absolute 24-hour price change percentage."""

        return abs(self.price_change_percentage_24h)

    @property
    def range_percentage(self) -> float | None:
        """Return the 24-hour high/low range as a percentage of the low."""

        if self.high_price_24h is None or self.low_price_24h is None:
            return None

        return (
            (self.high_price_24h - self.low_price_24h)
            / self.low_price_24h
            * 100
        )


@dataclass(frozen=True, slots=True)
class FuturesScreenerConfig:
    """Cheap deterministic futures-screening thresholds."""

    minimum_quote_volume_24h: float = 0.0
    maximum_spread_percentage: float = 100.0
    minimum_absolute_movement_percentage: float = 0.0
    shortlist_size: int = 30

    def __post_init__(self) -> None:
        if self.minimum_quote_volume_24h < 0:
            raise ValueError("minimum_quote_volume_24h cannot be negative")
        if self.maximum_spread_percentage < 0:
            raise ValueError("maximum_spread_percentage cannot be negative")
        if self.minimum_absolute_movement_percentage < 0:
            raise ValueError(
                "minimum_absolute_movement_percentage cannot be negative"
            )
        if self.shortlist_size <= 0:
            raise ValueError("shortlist_size must be positive")


class FuturesScreeningExclusionReason(StrEnum):
    """Why a contract or ticker did not enter screening results."""

    OUTSIDE_UNIVERSE = "outside_universe"
    MISSING_TICKER = "missing_ticker"
    INSUFFICIENT_LIQUIDITY = "insufficient_liquidity"
    SPREAD_TOO_WIDE = "spread_too_wide"
    INSUFFICIENT_MOVEMENT = "insufficient_movement"


@dataclass(frozen=True, slots=True)
class FuturesScreeningExclusion:
    """One explicit lightweight-screening exclusion."""

    exchange_symbol: str
    reason: FuturesScreeningExclusionReason
    detail: str

    def __post_init__(self) -> None:
        _require_text("exchange_symbol", self.exchange_symbol)
        _require_text("detail", self.detail)


@dataclass(frozen=True, slots=True)
class FuturesScreeningCandidate:
    """One eligible and deterministically ranked futures contract."""

    rank: int
    contract: FuturesContractMetadata
    ticker: FuturesTickerSnapshot

    def __post_init__(self) -> None:
        if self.rank <= 0:
            raise ValueError("rank must be positive")


@dataclass(frozen=True, slots=True)
class FuturesScreeningResult:
    """Complete typed result of one lightweight futures screening pass."""

    total_contracts: int
    total_tickers: int
    candidates: tuple[FuturesScreeningCandidate, ...]
    exclusions: tuple[FuturesScreeningExclusion, ...]

    def __post_init__(self) -> None:
        if self.total_contracts < 0:
            raise ValueError("total_contracts cannot be negative")
        if self.total_tickers < 0:
            raise ValueError("total_tickers cannot be negative")

    @property
    def shortlisted_count(self) -> int:
        """Return the number of ranked candidates."""

        return len(self.candidates)
