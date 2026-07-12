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
    """Normalized OHLCV candle."""

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
