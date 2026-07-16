"""Environment-aware near-current entry decisions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from apex.application.market_strategy_router import (
    MarketStrategyRoute,
    PreferredDirection,
    strategy_allowed_for_direction,
)
from apex.market_environment import ExtensionState, MarketEnvironment, VolatilityState
from apex.strategies import StrategyType, TradeDirection


class ChaseRisk(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


@dataclass