"""Application configuration loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from apex.config.futures_screener import FuturesScreenerSettings
from apex.config.methodology import MethodologySettings
from apex.data.timeframes import timeframe_delta
from apex.market_environment.config import MarketEnvironmentConfig
from apex.strategies import StrategyType

MethodologyGateModeSetting = Literal["shadow", "enforce"]

_VALID_TIMEFRAME_ROLES = {
    "long_term_macro",
    "swing",
    "macro",
    "intermediate",
    "intraday",
    "setup",
    "entry",
    "refinement",
    "timing",
}

_THESIS_TIMEFRAME_ROLES = {
    "long_term_macro",
    "swing",
    "macro",
    "intermediate",
    "intraday",
    "setup",
    "entry",
}

DEFAULT_TIMEFRAME_ROLES: dict[str, str] = {
    "1W": "long_term_macro",
    "3D": "swing",
    "1D": "swing",
    "12h": "swing",
    "8h": "macro",
    "6h": "macro",
    "4h": "macro",
    "2h": "intermediate",
    "1h": "intermediate",
    "30m": "intraday",
    "15m": "setup",
    "5m": "entry",
    "3m": "refinement",
    "1m": "timing",
}

DEFAULT_TIMEFRAME_RESAMPLING_SOURCES: dict[str, str] = {
    "1W": "4h",
    "3D": "4h",
    "1D": "4h",
    "12h": "4h",
    "8h": "4h",
    "6h": "1h",
    "2h": "1h",
}

DEFAULT_TIMEFRAME_MAX_STALENESS_SECONDS: dict[str, int] = {
    "1m": 180,
    "3m": 360,
    "5m": 600,
    "15m": 1_800,
    "30m": 3_600,
    "1h": 7_200,
    "2h": 14_400,
    "4h": 28_800,
    "6h": 43_200,
    "8h": 57_600,
    "12h": 86_400,
    "1D": 259_200,
    "3D": 604_800,
    "1W": 1_209_600,
}

DEFAULT_STRATEGY_ROUTING: dict[str, list[str]] = {
    "enabled": [strategy.value for strategy in StrategyType],
}


class TimeframeIndicatorSettings(BaseModel):
    """Candle-period profile for one analytical timeframe role."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ema_fast: int = Field(default=20, ge=2)
    ema_slow: int = Field(default=50, ge=3)
    rsi: int = Field(default=14, ge=2)
    rsi_slope: int = Field(default=3, ge=1)
    roc: int = Field(default=12, ge=1)
    macd_fast: int = Field(default=12, ge=2)
    macd_slow: int = Field(default=26, ge=3)
    macd_signal: int = Field(default=9, ge=1)
    atr: int = Field(default=14, ge=2)
    relative_volume: int = Field(default=20, ge=2)
    range_lookback: int = Field(default=20, ge=2)

    @model_validator(mode="after")
    def _validate_period_order(self) -> Self:
        if self.ema_fast >= self.ema_slow:
            raise ValueError("fast EMA period must be lower than slow EMA period")
        if self.macd_fast >= self.macd_slow:
            raise ValueError("fast MACD period must be lower than slow MACD period")
        return self


DEFAULT_TIMEFRAME_INDICATOR_PROFILES: dict[str, TimeframeIndicatorSettings] = {
    # Each role is calibrated to its candle horizon. Short horizons react faster;
    # higher horizons smooth noise without changing strategy or execution authority.
    "timing": TimeframeIndicatorSettings(
        ema_fast=7,
        ema_slow=18,
        rsi=7,
        rsi_slope=2,
        roc=4,
        macd_fast=4,
        macd_slow=10,
        macd_signal=3,
        atr=7,
        relative_volume=12,
        range_lookback=12,
    ),
    "refinement": TimeframeIndicatorSettings(
        ema_fast=9,
        ema_slow=21,
        rsi=9,
        rsi_slope=3,
        roc=6,
        macd_fast=5,
        macd_slow=13,
        macd_signal=4,
        atr=9,
        relative_volume=16,
        range_lookback=16,
    ),
    "entry": TimeframeIndicatorSettings(
        ema_fast=12,
        ema_slow=26,
        rsi=10,
        rsi_slope=3,
        roc=8,
        macd_fast=8,
        macd_slow=21,
        macd_signal=5,
        atr=10,
        relative_volume=20,
        range_lookback=20,
    ),
    "setup": TimeframeIndicatorSettings(
        ema_fast=20,
        ema_slow=50,
        rsi=14,
        rsi_slope=3,
        roc=12,
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        atr=14,
        relative_volume=24,
        range_lookback=24,
    ),
    "intraday": TimeframeIndicatorSettings(
        ema_fast=21,
        ema_slow=50,
        rsi=14,
        rsi_slope=4,
        roc=14,
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        atr=14,
        relative_volume=24,
        range_lookback=30,
    ),
    "intermediate": TimeframeIndicatorSettings(
        ema_fast=24,
        ema_slow=50,
        rsi=14,
        rsi_slope=4,
        roc=18,
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        atr=14,
        relative_volume=30,
        range_lookback=36,
    ),
    "macro": TimeframeIndicatorSettings(
        ema_fast=30,
        ema_slow=50,
        rsi=14,
        rsi_slope=5,
        roc=20,
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        atr=14,
        relative_volume=36,
        range_lookback=40,
    ),
    "swing": TimeframeIndicatorSettings(
        ema_fast=34,
        ema_slow=50,
        rsi=14,
        rsi_slope=5,
        roc=24,
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        atr=14,
        relative_volume=40,
        range_lookback=48,
    ),
    "long_term_macro": TimeframeIndicatorSettings(
        ema_fast=40,
        ema_slow=50,
        rsi=14,
        rsi_slope=6,
        roc=30,
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        atr=14,
        relative_volume=50,
        range_lookback=50,
    ),
}

_VALID_STRATEGY_ROUTE_KEYS = frozenset(DEFAULT_STRATEGY_ROUTING)


class GeometryExecutionProfileSettings(BaseModel):
    """One explicit round-trip execution profile in percentage points."""

    model_config = ConfigDict(extra="forbid")

    entry_fee_pct: float = Field(ge=0)
    exit_fee_pct: float = Field(ge=0)
    entry_slippage_pct: float = Field(ge=0)
    exit_slippage_pct: float = Field(ge=0)


class GeometryExecutionSettings(BaseModel):
    """Order-intent-aware execution assumptions for geometry auditing."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    include_observed_spread_in_cost: bool = False
    market: GeometryExecutionProfileSettings | None = None
    limit: GeometryExecutionProfileSettings | None = None

    entry_fee_pct: float | None = Field(default=None, ge=0)
    exit_fee_pct: float | None = Field(default=None, ge=0)
    entry_slippage_pct: float | None = Field(default=None, ge=0)
    exit_slippage_pct: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate_complete_enabled_costs(self) -> Self:
        legacy = (
            self.entry_fee_pct,
            self.exit_fee_pct,
            self.entry_slippage_pct,
            self.exit_slippage_pct,
        )
        legacy_complete = all(value is not None for value in legacy)
        legacy_partial = any(value is not None for value in legacy) and not legacy_complete
        if legacy_partial:
            raise ValueError("legacy geometry execution costs require entry/exit fees and slippage")
        if self.enabled and self.market is None and not legacy_complete:
            raise ValueError(
                "enabled geometry execution costs require a market profile or complete "
                "legacy entry/exit fees and slippage"
            )

        # Preserve the legacy scalar interface for existing callers while the
        # explicit market/limit profiles remain the canonical configuration.
        if self.market is not None and not legacy_complete:
            self.entry_fee_pct = self.market.entry_fee_pct
            self.exit_fee_pct = self.market.exit_fee_pct
            self.entry_slippage_pct = self.market.entry_slippage_pct
            self.exit_slippage_pct = self.market.exit_slippage_pct

        return self


class FileSettings(BaseModel):
    """Validated settings loaded from the default YAML file."""

    model_config = ConfigDict(extra="forbid")

    environment: str = "development"
    log_level: str = "INFO"
    data_dir: Path = Path("data")
    log_dir: Path = Path("logs")
    cache_enabled: bool = True
    methodology_gate_mode: MethodologyGateModeSetting = "shadow"
    market_environment: MarketEnvironmentConfig = Field(default_factory=MarketEnvironmentConfig)
    methodology: MethodologySettings = Field(default_factory=MethodologySettings)
    futures_evidence_enabled: bool = True
    outcome_tracking_enabled: bool = True
    rollout_diagnostics_enabled: bool = False
    geometry_execution: GeometryExecutionSettings = Field(default_factory=GeometryExecutionSettings)
    futures_screener: FuturesScreenerSettings = Field(default_factory=FuturesScreenerSettings)
    analysis_timeframes: list[str] = Field(default_factory=list)
    timeframe_roles: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_TIMEFRAME_ROLES))
    timeframe_resampling_sources: dict[str, str] = Field(
        default_factory=lambda: dict(DEFAULT_TIMEFRAME_RESAMPLING_SOURCES)
    )
    timeframe_max_staleness_seconds: dict[str, int] = Field(
        default_factory=lambda: dict(DEFAULT_TIMEFRAME_MAX_STALENESS_SECONDS)
    )
    timeframe_indicator_profiles: dict[str, TimeframeIndicatorSettings] = Field(
        default_factory=lambda: dict(DEFAULT_TIMEFRAME_INDICATOR_PROFILES)
    )
    strategy_routing: dict[str, list[str]] = Field(
        default_factory=lambda: {
            key: list(values) for key, values in DEFAULT_STRATEGY_ROUTING.items()
        }
    )

    @field_validator("analysis_timeframes")
    @classmethod
    def _validate_analysis_timeframes(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if len(set(normalized)) != len(normalized):
            raise ValueError("analysis timeframes cannot contain duplicates")
        return normalized

    @field_validator("timeframe_roles")
    @classmethod
    def _validate_timeframe_roles(cls, value: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for timeframe, role in value.items():
            clean_timeframe = timeframe.strip()
            clean_role = role.strip().lower()
            if not clean_timeframe:
                raise ValueError("timeframe role keys cannot be empty")
            if clean_role not in _VALID_TIMEFRAME_ROLES:
                raise ValueError(f"unsupported timeframe role for {clean_timeframe}: {role}")
            normalized[clean_timeframe] = clean_role
        if len(normalized) != len(value):
            raise ValueError("timeframe role keys must be unique after normalization")
        return normalized

    @field_validator("timeframe_resampling_sources")
    @classmethod
    def _validate_timeframe_resampling_sources(cls, value: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for target, source in value.items():
            clean_target = target.strip()
            clean_source = source.strip()
            if not clean_target or not clean_source:
                raise ValueError("resampling timeframe keys and values cannot be empty")
            if clean_target == clean_source:
                raise ValueError("resampling source must differ from target timeframe")
            normalized[clean_target] = clean_source
        if len(normalized) != len(value):
            raise ValueError("resampling target keys must be unique after normalization")
        return normalized

    @field_validator("timeframe_max_staleness_seconds")
    @classmethod
    def _validate_timeframe_max_staleness_seconds(cls, value: dict[str, int]) -> dict[str, int]:
        normalized: dict[str, int] = {}
        for timeframe, seconds in value.items():
            clean_timeframe = timeframe.strip()
            if not clean_timeframe:
                raise ValueError("staleness timeframe keys cannot be empty")
            if seconds < 0:
                raise ValueError(f"staleness seconds cannot be negative for {clean_timeframe}")
            normalized[clean_timeframe] = seconds
        if len(normalized) != len(value):
            raise ValueError("staleness timeframe keys must be unique after normalization")
        return normalized

    @field_validator("strategy_routing")
    @classmethod
    def _validate_strategy_routing(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        normalized: dict[str, list[str]] = {}
        unknown_routes = sorted(set(value) - _VALID_STRATEGY_ROUTE_KEYS)
        if unknown_routes:
            raise ValueError(f"unsupported strategy routing keys: {', '.join(unknown_routes)}")
        missing_routes = sorted(_VALID_STRATEGY_ROUTE_KEYS - set(value))
        if missing_routes:
            raise ValueError(f"missing strategy routing keys: {', '.join(missing_routes)}")
        valid_strategy_values = {strategy.value for strategy in StrategyType}
        for route_key, strategies in value.items():
            if not strategies:
                raise ValueError(f"strategy routing for {route_key} cannot be empty")
            clean_strategies: list[str] = []
            for strategy in strategies:
                clean_strategy = strategy.strip()
                if clean_strategy not in valid_strategy_values:
                    raise ValueError(f"unsupported strategy in {route_key}: {strategy}")
                clean_strategies.append(clean_strategy)
            if len(set(clean_strategies)) != len(clean_strategies):
                raise ValueError(f"strategy routing for {route_key} cannot contain duplicates")
            normalized[route_key] = clean_strategies
        return normalized

    @field_validator("timeframe_indicator_profiles")
    @classmethod
    def _validate_timeframe_indicator_profiles(
        cls, value: dict[str, TimeframeIndicatorSettings]
    ) -> dict[str, TimeframeIndicatorSettings]:
        unknown = sorted(set(value) - _VALID_TIMEFRAME_ROLES)
        if unknown:
            raise ValueError(f"unsupported indicator profile roles: {', '.join(unknown)}")
        missing = sorted(_VALID_TIMEFRAME_ROLES - set(value))
        if missing:
            raise ValueError(f"missing indicator profile roles: {', '.join(missing)}")
        return value

    @model_validator(mode="after")
    def _validate_enabled_timeframe_roles(self) -> Self:
        missing = [
            timeframe
            for timeframe in self.analysis_timeframes
            if timeframe not in self.timeframe_roles
        ]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"analysis timeframes missing role configuration: {joined}")
        enabled_roles = [self.timeframe_roles[timeframe] for timeframe in self.analysis_timeframes]
        if len(set(enabled_roles)) != len(enabled_roles):
            raise ValueError("enabled analysis timeframes must map to unique roles")
        if enabled_roles and not any(role in _THESIS_TIMEFRAME_ROLES for role in enabled_roles):
            raise ValueError("enabled analysis timeframes must include a thesis role")
        for target, source in self.timeframe_resampling_sources.items():
            if target not in self.timeframe_roles:
                raise ValueError(f"resampling target lacks role configuration: {target}")
            if timeframe_delta(target) <= timeframe_delta(source):
                raise ValueError(f"resampling target must be higher than source: {target}")
        missing_staleness = [
            timeframe
            for timeframe in self.analysis_timeframes
            if timeframe not in self.timeframe_max_staleness_seconds
        ]
        if missing_staleness:
            joined = ", ".join(missing_staleness)
            raise ValueError(f"analysis timeframes missing staleness configuration: {joined}")
        return self


class EnvironmentSettings(BaseSettings):
    """Environment overrides for bootstrapping Apex."""

    model_config = SettingsConfigDict(env_prefix="APEX_", env_file=".env", extra="ignore")

    environment: str | None = None
    log_level: str | None = None
    config_dir: Path = Path("config")
    data_dir: Path | None = None
    log_dir: Path | None = None


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Configuration root must be a mapping: {path}")
    return payload


def load_settings(config_dir: Path | None = None) -> FileSettings:
    """Load YAML settings and apply environment overrides."""

    env = EnvironmentSettings()
    resolved_config_dir = config_dir or env.config_dir
    raw = _read_yaml(resolved_config_dir / "default.yaml")

    overrides = {
        "environment": env.environment,
        "log_level": env.log_level,
        "data_dir": env.data_dir,
        "log_dir": env.log_dir,
    }
    raw.update({key: value for key, value in overrides.items() if value is not None})
    return FileSettings.model_validate(raw)
