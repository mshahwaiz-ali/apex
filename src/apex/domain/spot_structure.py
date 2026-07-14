"""Higher-timeframe structure contracts for spot analysis."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.domain.spot import SpotMarketRegime
from apex.domain.spot_market import SpotMarketBreadthSnapshot


class SpotTrendState(StrEnum):
    STRONG_UPTREND = "STRONG_UPTREND"
    UPTREND = "UPTREND"
    RANGE = "RANGE"
    DOWNTREND = "DOWNTREND"
    STRONG_DOWNTREND = "STRONG_DOWNTREND"


class SpotExtensionState(StrEnum):
    NORMAL = "NORMAL"
    EXTENDED = "EXTENDED"
    TERMINAL = "TERMINAL"
    DOWNSIDE_RISK = "DOWNSIDE_RISK"


class SpotZoneType(StrEnum):
    SUPPORT = "SUPPORT"
    RESISTANCE = "RESISTANCE"
    DEMAND = "DEMAND"


class SpotTimeframeSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    timeframe: str
    close: float = Field(gt=0)
    ema_fast: float = Field(gt=0)
    ema_slow: float = Field(gt=0)
    swing_high: float = Field(gt=0)
    swing_low: float = Field(gt=0)
    atr: float = Field(gt=0)
    higher_high: bool
    higher_low: bool
    lower_high: bool
    lower_low: bool
    relative_strength_percentage: float | None = None

    @model_validator(mode="after")
    def validate_geometry(self) -> Self:
        if self.swing_low >= self.swing_high:
            raise ValueError("spot swing low must be below swing high")
        return self


class SpotStructureThresholds(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    approved_timeframes: tuple[str, ...] = ("1w", "1d", "12h", "8h", "4h")
    extension_atr_multiple: float = Field(default=2.5, gt=0)
    terminal_extension_atr_multiple: float = Field(default=4.0, gt=0)
    downside_risk_atr_multiple: float = Field(default=1.5, gt=0)
    zone_half_width_atr_multiple: float = Field(default=0.35, gt=0)
    risk_on_minimum_breadth_percentage: float = Field(default=60.0, ge=0, le=100)
    risk_off_maximum_breadth_percentage: float = Field(default=35.0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.extension_atr_multiple >= self.terminal_extension_atr_multiple:
            raise ValueError("terminal extension threshold must be larger")
        if self.risk_off_maximum_breadth_percentage >= self.risk_on_minimum_breadth_percentage:
            raise ValueError("risk-off breadth must be below risk-on breadth")
        return self


class SpotPriceZone(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    zone_type: SpotZoneType
    lower: float = Field(gt=0)
    upper: float = Field(gt=0)
    source_timeframe: str

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.lower > self.upper:
            raise ValueError("zone lower bound cannot exceed upper bound")
        return self


class SpotTimeframeStructure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    timeframe: str
    trend: SpotTrendState
    extension: SpotExtensionState
    support: SpotPriceZone
    resistance: SpotPriceZone
    demand: SpotPriceZone
    evidence: tuple[str, ...]


class SpotStructureResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trend: SpotTrendState
    extension: SpotExtensionState
    timeframes: tuple[SpotTimeframeStructure, ...]
    relative_strength_score: float | None = None
    evidence: tuple[str, ...]


class SpotRegimeInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    btc_trend: SpotTrendState
    btc_extension: SpotExtensionState
    breadth: SpotMarketBreadthSnapshot
    btc_return_percentage: float | None = None
    market_drawdown_percentage: float | None = Field(default=None, ge=0)


class SpotRegimeResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    regime: SpotMarketRegime
    allow_new_entries: bool
    evidence: tuple[str, ...]
