"""Application configuration loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FileSettings(BaseModel):
    """Validated settings loaded from the default YAML file."""

    model_config = ConfigDict(extra="forbid")

    environment: str = "development"
    log_level: str = "INFO"
    data_dir: Path = Path("data")
    log_dir: Path = Path("logs")
    cache_enabled: bool = True
    analysis_timeframes: list[str] = Field(default_factory=list)


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
