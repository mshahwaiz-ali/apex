"""Application configuration loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from apex.data.timeframes import timeframe_delta
from apex.domain import GainerStateThresholds
from apex.strategies import StrategyType

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
    "normal_market": [
        StrategyType.TREND_PULLBACK.value,
        StrategyType.BREAKOUT_CONTINUATION.value,
        StrategyType.LIQUIDITY_REVERSAL.value,
        StrategyType.RANGE_REVERSAL.value,
        StrategyType.MOMENTUM_CONTINUATION.value,
    ],
    "gainer": [
        StrategyType.MOMENTUM_GAINER_CONTINUATION.value,
        StrategyType.MOMENTUM_CONTINUATION.value,
        StrategyType.BREAKOUT_CONTINUATION.value,
    ],
}

_VALID_STRATEGY_ROUTE_KEYS = frozenset(DEFAULT_STRATEGY_ROUTING)


class FileSettings(BaseModel):
    """Validated settings loaded from the default YAML file."""

    model_config = ConfigDict(extra="forbid")

    environment: str = "development"
    log_level: str = "INFO"
    data_dir: Path = Path("data")
    log_dir: Path = Path("logs")
    cache_enabled: bool = True
    analysis_timeframes: list[str] = Field(default_factory=list)
    timeframe_roles: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_TIMEFRAME_ROLES))
    timeframe_resampling_sources: dict[str, str] = Field(
        default_factory=lambda: dict(DEFAULT_TIMEFRAME_RESAMPLING_SOURCES)
    )
    timeframe_max_staleness_seconds: dict[str, int] = Field(
        default_factory=lambda: dict(DEFAULT_TIMEFRAME_MAX_STALENESS_SECONDS)
    )
    advanced_intelligence_enabled: bool = False
    intelligence_funding_enabled: bool = False
    intelligence_open_interest_enabled: bool = False
    intelligence_correlation_enabled: bool = False
    gainer_state_thresholds: GainerStateThresholds = Field(default_factory=GainerStateThresholds)
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
