"""Validated thresholds for S3 spot strategies."""

from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SpotStrategyConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    minimum_volume_ratio: float = Field(default=1.2, ge=0)
    breakout_volume_ratio: float = Field(default=1.5, ge=0)
    maximum_pullback_depth_percentage: float = Field(default=12.0, gt=0)
    maximum_accumulation_range_width_percentage: float = Field(default=18.0, gt=0)
    minimum_relative_strength_percentage: float = Field(default=3.0)
    invalidation_buffer_percentage: float = Field(default=1.0, gt=0, le=20)

    @model_validator(mode="after")
    def validate_threshold_order(self) -> Self:
        if self.breakout_volume_ratio < self.minimum_volume_ratio:
            raise ValueError("breakout volume threshold cannot be below minimum volume threshold")
        return self


def load_spot_strategy_config(path: str | Path) -> SpotStrategyConfig:
    raw: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("spot strategy configuration must contain a mapping")
    return SpotStrategyConfig.model_validate(raw)
