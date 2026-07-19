"""Core provider-independent domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Decision(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    NO_TRADE = "NO_TRADE"


class Candle(BaseModel):
    """Normalized Binance-compatible candle with optional participation fields."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)
    quote_volume: float | None = Field(default=None, ge=0)
    trade_count: int | None = Field(default=None, ge=0)
    taker_buy_base_volume: float | None = Field(default=None, ge=0)
    taker_buy_quote_volume: float | None = Field(default=None, ge=0)
    is_closed: bool
    source: str

    @model_validator(mode="after")
    def validate_market_bounds(self) -> Candle:
        if self.close_time <= self.open_time:
            raise ValueError("close_time must be after open_time")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be greater than or equal to all OHLC values")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be less than or equal to all OHLC values")
        return self


class TickerSnapshot(BaseModel):
    """Normalized current-market ticker information."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    last_price: float = Field(gt=0)
    bid_price: float = Field(gt=0)
    ask_price: float = Field(gt=0)
    quote_volume_24h: float = Field(ge=0)
    captured_at: datetime
    source: str

    @model_validator(mode="after")
    def validate_prices(self) -> TickerSnapshot:
        if self.bid_price > self.ask_price:
            raise ValueError("bid price cannot exceed ask price")
        return self

    @property
    def spread(self) -> float:
        """Return the absolute bid/ask spread."""

        return self.ask_price - self.bid_price

    @property
    def spread_percentage(self) -> float:
        """Return spread as a percentage of the midpoint price."""

        midpoint = (self.bid_price + self.ask_price) / 2
        return (self.spread / midpoint) * 100


class OrderBookLevel(BaseModel):
    """One normalized order-book price level."""

    model_config = ConfigDict(frozen=True)

    price: float = Field(gt=0)
    quantity: float = Field(ge=0)

    @property
    def notional(self) -> float:
        return self.price * self.quantity


class OrderBookSnapshot(BaseModel):
    """Provider-independent top-of-book/depth snapshot."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]
    captured_at: datetime
    source: str

    @model_validator(mode="after")
    def validate_book(self) -> OrderBookSnapshot:
        if not self.bids or not self.asks:
            raise ValueError("order book requires at least one bid and ask")
        if tuple(sorted(self.bids, key=lambda level: level.price, reverse=True)) != self.bids:
            raise ValueError("order book bids must be sorted descending by price")
        if tuple(sorted(self.asks, key=lambda level: level.price)) != self.asks:
            raise ValueError("order book asks must be sorted ascending by price")
        if self.best_bid.price > self.best_ask.price:
            raise ValueError("order book best bid cannot exceed best ask")
        return self

    @property
    def best_bid(self) -> OrderBookLevel:
        return self.bids[0]

    @property
    def best_ask(self) -> OrderBookLevel:
        return self.asks[0]

    @property
    def spread_percentage(self) -> float:
        midpoint = (self.best_bid.price + self.best_ask.price) / 2
        return (self.best_ask.price - self.best_bid.price) / midpoint * 100

    @property
    def bid_depth_notional(self) -> float:
        return sum(level.notional for level in self.bids)

    @property
    def ask_depth_notional(self) -> float:
        return sum(level.notional for level in self.asks)

    @property
    def depth_imbalance(self) -> float:
        total = self.bid_depth_notional + self.ask_depth_notional
        if total <= 0:
            return 0.0
        return (self.bid_depth_notional - self.ask_depth_notional) / total


class ExchangeFilterSnapshot(BaseModel):
    """Provider-independent futures precision and notional filters."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    tick_size: float = Field(gt=0)
    step_size: float = Field(gt=0)
    min_quantity: float = Field(ge=0)
    min_notional: float = Field(ge=0)
    captured_at: datetime
    source: str


class EntryZone(BaseModel):
    model_config = ConfigDict(frozen=True)
    low: float = Field(gt=0)
    high: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_order(self) -> EntryZone:
        if self.low > self.high:
            raise ValueError("entry zone low cannot exceed high")
        return self


class TakeProfit(BaseModel):
    model_config = ConfigDict(frozen=True)
    label: str
    price: float = Field(gt=0)
    risk_reward: float = Field(gt=0)


class AnalysisResult(BaseModel):
    """Top-level result shape used by CLI and later storage layers."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    decision: Decision
    generated_at: datetime
    reasons: tuple[str, ...] = ()
    confidence_score: float | None = Field(default=None, ge=0, le=100)
