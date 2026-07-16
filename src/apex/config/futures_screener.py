"""Configuration for lightweight futures-market screening."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from apex.domain.futures_screening import FuturesScreenerConfig


class FuturesScreenerSettings(BaseModel):
    """Validated runtime settings for the lightweight futures screener."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    minimum_quote_volume_24h: float = Field(
        default=5_000_000.0,
        ge=0,
    )
    maximum_spread_percentage: float = Field(
        default=0.25,
        ge=0,
    )
    minimum_absolute_movement_percentage: float = Field(
        default=1.0,
        ge=0,
    )
    shortlist_size: int = Field(
        default=30,
        gt=0,
    )
    quote_asset: str = Field(
        default="USDT",
        min_length=1,
    )
    blacklist: tuple[str, ...] = ()
    allowlist: tuple[str, ...] | None = None
    metadata_cache_ttl_seconds: int = Field(
        default=3600,
        gt=0,
    )

    @field_validator("quote_asset")
    @classmethod
    def _normalize_quote_asset(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("futures screener quote asset cannot be empty")
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
        """Convert validated file settings into the domain screening contract."""

        return FuturesScreenerConfig(
            minimum_quote_volume_24h=self.minimum_quote_volume_24h,
            maximum_spread_percentage=self.maximum_spread_percentage,
            minimum_absolute_movement_percentage=(
                self.minimum_absolute_movement_percentage
            ),
            shortlist_size=self.shortlist_size,
        )


def _normalize_symbols(
    values: tuple[str, ...],
    label: str,
) -> tuple[str, ...]:
    normalized = tuple(
        value.strip().upper()
        for value in values
        if value.strip()
    )
    if len(normalized) != len(values):
        raise ValueError(f"futures screener {label} cannot contain empty symbols")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"futures screener {label} cannot contain duplicates")
    return normalized
