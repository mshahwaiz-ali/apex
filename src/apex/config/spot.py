"""Validated spot product configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SpotAllocationConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    maximum_allocation_per_position_percentage: float = Field(gt=0, le=100)
    maximum_total_spot_exposure_percentage: float = Field(gt=0, le=100)
    maximum_correlated_sector_exposure_percentage: float = Field(gt=0, le=100)
    minimum_quote_reserve_percentage: float = Field(ge=0, lt=100)
    maximum_open_positions: int = Field(gt=0)
    maximum_account_loss_percentage: float = Field(gt=0, le=100)

    @model_validator(mode="after")
    def validate_allocation_limits(self) -> Self:
        if self.maximum_allocation_per_position_percentage > self.maximum_total_spot_exposure_percentage:
            raise ValueError("per-position allocation cannot exceed total spot exposure")
        if self.maximum_total_spot_exposure_percentage + self.minimum_quote_reserve_percentage > 100:
            raise ValueError("spot exposure and minimum quote reserve cannot exceed 100 percent")
        return self


class SpotEntryConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    maximum_entry_legs: int = Field(default=3, ge=1, le=3)
    default_entry_allocations: tuple[float, ...] = (40.0, 35.0, 25.0)
    maximum_chase_percentage: float = Field(gt=0, le=100)

    @model_validator(mode="after")
    def validate_entry_allocations(self) -> Self:
        if len(self.default_entry_allocations) > self.maximum_entry_legs:
            raise ValueError("default spot entries exceed maximum entry legs")
        if any(value <= 0 or value > 100 for value in self.default_entry_allocations):
            raise ValueError("spot entry allocations must be within (0, 100]")
        if abs(sum(self.default_entry_allocations) - 100.0) > 1e-9:
            raise ValueError("default spot entry allocations must total 100")
        return self


class SpotExitConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    default_target_allocations: tuple[float, ...] = (25.0, 35.0, 25.0, 15.0)
    maximum_holding_days: int = Field(default=7, gt=0)
    review_interval_hours: int = Field(default=24, gt=0)

    @model_validator(mode="after")
    def validate_target_allocations(self) -> Self:
        if any(value <= 0 or value > 100 for value in self.default_target_allocations):
            raise ValueError("spot target allocations must be within (0, 100]")
        if abs(sum(self.default_target_allocations) - 100.0) > 1e-9:
            raise ValueError("default spot target allocations must total 100")
        return self


class SpotProductConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    spot_only: bool = True
    long_only: bool = True
    leverage_allowed: bool = False
    borrowed_assets_allowed: bool = False
    primary_timeframes: tuple[str, ...] = ("1w", "1d", "12h", "4h")
    optional_execution_timeframes: tuple[str, ...] = ("1h",)
    forbidden_thesis_timeframes: tuple[str, ...] = ("1m", "3m", "5m")
    allocation: SpotAllocationConfig
    entry: SpotEntryConfig
    exit: SpotExitConfig

    @model_validator(mode="after")
    def validate_product_contract(self) -> Self:
        if not self.spot_only:
            raise ValueError("Apex spot configuration must remain spot-only")
        if not self.long_only:
            raise ValueError("initial Apex spot configuration must remain long-only")
        if self.leverage_allowed:
            raise ValueError("initial Apex spot configuration cannot enable leverage")
        if self.borrowed_assets_allowed:
            raise ValueError("initial Apex spot configuration cannot enable borrowed assets")
        thesis = set(self.primary_timeframes)
        forbidden = set(self.forbidden_thesis_timeframes)
        if thesis & forbidden:
            raise ValueError("forbidden lower timeframes cannot influence the spot thesis")
        if len(thesis) != len(self.primary_timeframes):
            raise ValueError("spot primary timeframes must be unique")
        return self


def load_spot_product_config(path: str | Path) -> SpotProductConfig:
    """Load the spot product contract from YAML."""

    raw: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("spot configuration file must contain a mapping")
    return SpotProductConfig.model_validate(raw)
