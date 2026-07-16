"""Validated configuration for market-environment classification and fusion."""

from __future__ import annotations

from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class MarketEnvironmentConfig(BaseModel):
    """Strict thresholds and weights for deterministic environment analysis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    required_timeframes: tuple[str, ...] = ("1m", "3m", "5m", "15m", "30m", "1h", "4h")
    timeframe_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "1m": 0.05,
            "3m": 0.10,
            "5m": 0.15,
            "15m": 0.20,
            "30m": 0.20,
            "1h": 0.15,
            "4h": 0.15,
        }
    )
    higher_timeframes: tuple[str, ...] = ("4h", "1h")
    structure_timeframes: tuple[str, ...] = ("30m", "15m")
    execution_priority: tuple[str, ...] = ("3m", "5m", "15m", "30m", "1h", "4h")
    entry_priority: tuple[str, ...] = ("1m", "3m", "5m", "15m")
    trend_strength_min: float = 0.55
    strong_trend_strength_min: float = 0.75
    relative_volume_expansion_min: float = 1.25
    relative_volume_extreme_min: float = 2.5
    volatility_compressed_max: float = 0.75
    volatility_expanding_min: float = 1.15
    volatility_extreme_min: float = 1.8
    retest_tolerance_atr: float = 0.35
    extension_moderate_atr: float = 1.25
    extension_overextended_atr: float = 2.0
    extension_extreme_atr: float = 3.0
    minimum_tradeability_score: float = 55.0
    maximum_tradeable_conflict_score: float = 60.0
    minimum_required_timeframes: int = 4
    maximum_missing_timeframes: int = 3

    @model_validator(mode="after")
    def validate_configuration(self) -> Self:
        if not self.required_timeframes:
            raise ValueError("required timeframes cannot be empty")
        if len(set(self.required_timeframes)) != len(self.required_timeframes):
            raise ValueError("required timeframes cannot contain duplicates")
        unknown_weights = sorted(set(self.timeframe_weights) - set(self.required_timeframes))
        missing_weights = sorted(set(self.required_timeframes) - set(self.timeframe_weights))
        if unknown_weights:
            raise ValueError(f"unknown timeframe weights: {', '.join(unknown_weights)}")
        if missing_weights:
            raise ValueError(f"missing timeframe weights: {', '.join(missing_weights)}")
        if any(weight <= 0 for weight in self.timeframe_weights.values()):
            raise ValueError("timeframe weights must be positive")
        if abs(sum(self.timeframe_weights.values()) - 1.0) > 1e-9:
            raise ValueError("timeframe weights must sum to one")
        configured = set(self.required_timeframes)
        for name in (
            "higher_timeframes",
            "structure_timeframes",
            "execution_priority",
            "entry_priority",
        ):
            values = getattr(self, name)
            unknown = sorted(set(values) - configured)
            if unknown:
                raise ValueError(f"unknown {name.replace('_', ' ')}: {', '.join(unknown)}")
            if len(set(values)) != len(values):
                raise ValueError(f"{name.replace('_', ' ')} cannot contain duplicates")
        bounded = (
            self.trend_strength_min,
            self.strong_trend_strength_min,
            self.volatility_compressed_max,
            self.volatility_expanding_min,
            self.volatility_extreme_min,
            self.minimum_tradeability_score,
            self.maximum_tradeable_conflict_score,
        )
        if any(value < 0 for value in bounded):
            raise ValueError("market-environment thresholds cannot be negative")
        if self.trend_strength_min >= self.strong_trend_strength_min:
            raise ValueError("strong trend threshold must exceed trend threshold")
        if self.volatility_compressed_max >= self.volatility_expanding_min:
            raise ValueError("compressed volatility threshold must be below expansion threshold")
        if self.volatility_expanding_min >= self.volatility_extreme_min:
            raise ValueError("extreme volatility threshold must exceed expansion threshold")
        if not (
            self.extension_moderate_atr
            < self.extension_overextended_atr
            < self.extension_extreme_atr
        ):
            raise ValueError("extension ATR bands must be strictly increasing")
        if not 0 <= self.minimum_tradeability_score <= 100:
            raise ValueError("minimum tradeability score must be between zero and 100")
        if not 0 <= self.maximum_tradeable_conflict_score <= 100:
            raise ValueError("maximum conflict score must be between zero and 100")
        if not 1 <= self.minimum_required_timeframes <= len(self.required_timeframes):
            raise ValueError("minimum required timeframes is invalid")
        if not 0 <= self.maximum_missing_timeframes < len(self.required_timeframes):
            raise ValueError("maximum missing timeframes is invalid")
        return self


DEFAULT_MARKET_ENVIRONMENT_CONFIG = MarketEnvironmentConfig()


def load_market_environment_config(
    path: str | Path = "config/market_environment.yaml",
) -> MarketEnvironmentConfig:
    """Load strict market-environment configuration from YAML."""

    config_path = Path(path)
    if not config_path.exists():
        return DEFAULT_MARKET_ENVIRONMENT_CONFIG
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("market-environment configuration root must be a mapping")
    return MarketEnvironmentConfig.model_validate(payload)
