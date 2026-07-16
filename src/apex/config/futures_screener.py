"""Configuration for lightweight futures-market screening."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

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
