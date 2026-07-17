"""Application configuration loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from apex.config.futures_screener import FuturesScreenerSettings
from apex.data.timeframes import timeframe_delta
from apex.str