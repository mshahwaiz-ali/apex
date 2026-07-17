"""Validated strategy-specific approval thresholds."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.strategies import StrategyType


class StrategyQualityClass(StrEnum):
    """Relative approval strictness for a strategy