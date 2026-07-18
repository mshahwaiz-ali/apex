"""Configuration for lightweight futures-market screening."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from apex.domain.futures_screening import (
    FuturesOpportunityWeights,
    FuturesScreenerConfig,
)


class FuturesOpportunityWeightSettings(BaseModel):
    """Validated opportunity-score weights."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    liquidity: float = Field(default=0.12, ge=0)
    movement: float = Field(default=0.12, ge=0)
    acceleration: float = Field(default=0.13, ge=0)
    relative_volume: float = Field(default=0.13, ge=0)
    volatility_usability: float = Field(default=0.10, ge=0)
    entry_freshness: float = Field(default=0.10, ge=0)
    structure_proximity: float = Field(default=0.08, ge=0)
    directional_clarity: float = Field(default=0.12, ge=0)
    spread_quality: float = Field(default=0.05, ge=0)
    noise_quality: float = Field(default=0.05, ge=0)

    @model_validator(mode="after")
    def _validate_total(
        self,
    ) -> FuturesOpportunityWeightSettings:
        if abs(sum(self.model_dump().values()) - 1.0) > 1e-9:
            raise ValueError("futures opportunity weights must sum to 1.0")
        return self

    def to_domain(self) -> FuturesOpportunityWeights:
        """Convert validated weights to the domain contract."""

        return FuturesOpportunityWeights(**self.model_dump())


class FuturesScreenerSettings(BaseModel):
    """Validated runtime settings for the lightweight futures screener."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    minimum_quote_volume_24h: float = Field(
        default=5_000_000.0,
        ge=0,
    )
    maximum_spread_percentage: float = Field(
        default=0.25,
        gt=0,
    )
    minimum_absolute_movement_percentage: float = Field(
        default=0.0,
        ge=0,
    )
    shortlist_size: int = Field(default=36, gt=0)
    ticker_prefilter_size: int = Field(default=120, gt=0)
    candle_timeframe: str = Field(default="5m", min_length=1)
    candle_limit: int = Field(default=49, ge=13, le=250)
    minimum_candle_count: int = Field(default=25, ge=13)
    target_quote_volume_24h: float = Field(
        default=100_000_000.0,
        gt=0,
    )
    target_movement_percentage: float = Field(
        default=8.0,
        gt=0,
    )
    target_relative_volume: float = Field(default=2.0, gt=0)
    target_atr_percentage: float = Field(default=2.0, gt=0)
    maximum_usable_atr_percentage: float = Field(
        default=6.0,
        gt=0,
    )
    maximum_extension_atr: float = Field(default=3.0, gt=0)
    weights: FuturesOpportunityWeightSettings = FuturesOpportunityWeightSettings()
    quote_asset: str = Field(default="USDT", min_length=1)
    blacklist: tuple[str, ...] = ()
    allowlist: tuple[str, ...] | None = None
    metadata_cache_ttl_seconds: int = Field(
        default=3600,
        gt=0,
    )

    @model_validator(mode="after")
    def _validate_geometry(self) -> FuturesScreenerSettings:
        if self.ticker_prefilter_size < self.shortlist_size:
            raise ValueError("ticker_prefilter_size cannot be below shortlist_size")
        if self.minimum_candle_count > self.candle_limit:
            raise ValueError("minimum_candle_count cannot exceed candle_limit")
        if self.maximum_usable_atr_percentage <= self.target_atr_percentage:
            raise ValueError("maximum_usable_atr_percentage must exceed target_atr_percentage")
        return self

    @field_validator("quote_asset")
    @classmethod
    def _normalize_quote_asset(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("futures screener quote asset cannot be empty")
        return normalized

    @field_validator("candle_timeframe")
    @classmethod
    def _normalize_timeframe(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("futures screener candle timeframe cannot be empty")
        return normalized

    @field_validator("blacklist")
    @classmethod
    def _normalize_blacklist(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _normalize_symbols(value, "blacklist")

    @field_validator("allowlist")
    @classmethod
    def _normalize_allowlist(
        cls,
        value: tuple[str, ...] | None,
    ) -> tuple[str, ...] | None:
        if value is None:
            return None
        return _normalize_symbols(value, "allowlist")

    def to_domain(self) -> FuturesScreenerConfig:
        """Convert file settings into the domain screening contract."""

        return FuturesScreenerConfig(
            minimum_quote_volume_24h=(self.minimum_quote_volume_24h),
            maximum_spread_percentage=(self.maximum_spread_percentage),
            minimum_absolute_movement_percentage=(self.minimum_absolute_movement_percentage),
            shortlist_size=self.shortlist_size,
            ticker_prefilter_size=self.ticker_prefilter_size,
            candle_timeframe=self.candle_timeframe,
            candle_limit=self.candle_limit,
            minimum_candle_count=self.minimum_candle_count,
            target_quote_volume_24h=(self.target_quote_volume_24h),
            target_movement_percentage=(self.target_movement_percentage),
            target_relative_volume=self.target_relative_volume,
            target_atr_percentage=self.target_atr_percentage,
            maximum_usable_atr_percentage=(self.maximum_usable_atr_percentage),
            maximum_extension_atr=self.maximum_extension_atr,
            weights=self.weights.to_domain(),
        )


def _normalize_symbols(
    values: tuple[str, ...],
    label: str,
) -> tuple[str, ...]:
    normalized = tuple(value.strip().upper() for value in values if value.strip())
    if len(normalized) != len(values):
        raise ValueError(f"futures screener {label} cannot contain empty symbols")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"futures screener {label} cannot contain duplicates")
    return normalized
