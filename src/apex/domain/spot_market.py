"""Provider-independent spot market metadata, scanner, and eligibility contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SpotScannerMode(StrEnum):
    ELIGIBLE = "eligible"
    WATCHLIST = "watchlist"
    ALL = "all"


class SpotEligibilityReason(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    INSUFFICIENT_QUOTE_VOLUME = "INSUFFICIENT_QUOTE_VOLUME"
    INSUFFICIENT_MARKET_HISTORY = "INSUFFICIENT_MARKET_HISTORY"
    SPREAD_TOO_WIDE = "SPREAD_TOO_WIDE"
    INSUFFICIENT_CANDLE_HISTORY = "INSUFFICIENT_CANDLE_HISTORY"
    DATA_GAPS = "DATA_GAPS"
    TERMINAL_EXTENSION = "TERMINAL_EXTENSION"
    INSUFFICIENT_ATR = "INSUFFICIENT_ATR"
    DOWNSIDE_VOLATILITY_TOO_HIGH = "DOWNSIDE_VOLATILITY_TOO_HIGH"
    EXCLUDED_SYMBOL = "EXCLUDED_SYMBOL"


class SpotMarketMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(min_length=1)
    base_asset: str = Field(min_length=1)
    quote_asset: str = Field(min_length=1)
    quote_volume_24h: float = Field(ge=0)
    spread_percentage: float | None = Field(default=None, ge=0)
    market_age_days: int | None = Field(default=None, ge=0)
    available_candle_count: int = Field(ge=0)
    has_data_gaps: bool = False
    atr_percentage: float | None = Field(default=None, ge=0)
    downside_volatility_percentage: float | None = Field(default=None, ge=0)
    terminal_extension: bool = False


class SpotRelativeStrengthSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(min_length=1)
    return_vs_btc_percentage: float | None = None
    return_vs_quote_percentage: float | None = None
    lookback_days: int = Field(gt=0)


class SpotMarketBreadthSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    advancing_assets: int = Field(ge=0)
    declining_assets: int = Field(ge=0)
    unchanged_assets: int = Field(default=0, ge=0)
    percentage_above_trend: float | None = Field(default=None, ge=0, le=100)

    @property
    def observed_assets(self) -> int:
        return self.advancing_assets + self.declining_assets + self.unchanged_assets


class SpotEligibilityThresholds(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    minimum_quote_volume_24h: float = Field(gt=0)
    minimum_market_age_days: int = Field(gt=0)
    maximum_spread_percentage: float = Field(gt=0)
    minimum_candle_count: int = Field(gt=0)
    minimum_atr_percentage: float = Field(ge=0)
    maximum_downside_volatility_percentage: float = Field(gt=0)
    excluded_symbols: tuple[str, ...] = ()


class SpotEligibilityResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    eligible: bool
    reasons: tuple[SpotEligibilityReason, ...]


def evaluate_spot_symbol_eligibility(
    metadata: SpotMarketMetadata,
    thresholds: SpotEligibilityThresholds,
) -> SpotEligibilityResult:
    """Evaluate deterministic spot eligibility without fabricating missing values."""

    reasons: list[SpotEligibilityReason] = []
    if metadata.symbol.upper() in {symbol.upper() for symbol in thresholds.excluded_symbols}:
        reasons.append(SpotEligibilityReason.EXCLUDED_SYMBOL)
    if metadata.quote_volume_24h < thresholds.minimum_quote_volume_24h:
        reasons.append(SpotEligibilityReason.INSUFFICIENT_QUOTE_VOLUME)
    if (
        metadata.market_age_days is None
        or metadata.market_age_days < thresholds.minimum_market_age_days
    ):
        reasons.append(SpotEligibilityReason.INSUFFICIENT_MARKET_HISTORY)
    if (
        metadata.spread_percentage is None
        or metadata.spread_percentage > thresholds.maximum_spread_percentage
    ):
        reasons.append(SpotEligibilityReason.SPREAD_TOO_WIDE)
    if metadata.available_candle_count < thresholds.minimum_candle_count:
        reasons.append(SpotEligibilityReason.INSUFFICIENT_CANDLE_HISTORY)
    if metadata.has_data_gaps:
        reasons.append(SpotEligibilityReason.DATA_GAPS)
    if metadata.terminal_extension:
        reasons.append(SpotEligibilityReason.TERMINAL_EXTENSION)
    if (
        metadata.atr_percentage is None
        or metadata.atr_percentage < thresholds.minimum_atr_percentage
    ):
        reasons.append(SpotEligibilityReason.INSUFFICIENT_ATR)
    if (
        metadata.downside_volatility_percentage is None
        or metadata.downside_volatility_percentage
        > thresholds.maximum_downside_volatility_percentage
    ):
        reasons.append(SpotEligibilityReason.DOWNSIDE_VOLATILITY_TOO_HIGH)
    if reasons:
        return SpotEligibilityResult(eligible=False, reasons=tuple(reasons))
    return SpotEligibilityResult(eligible=True, reasons=(SpotEligibilityReason.ELIGIBLE,))
