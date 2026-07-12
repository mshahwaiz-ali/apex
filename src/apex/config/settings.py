"""Application configuration loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    advanced_intelligence_enabled: bool = False
    intelligence_funding_enabled: bool = False
    intelligence_open_interest_enabled: bool = False
    intelligence_correlation_enabled: bool = False

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
