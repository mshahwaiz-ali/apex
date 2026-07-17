"""Immutable contracts for deterministic strategy candidate generation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from apex.strategies.strategy_types import StrategyType


class TradeDirection(StrEnum):
    LONG = "long