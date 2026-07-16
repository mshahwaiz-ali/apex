"""Environment-aware strategy eligibility and ranking."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.market_environment import (
    ConflictState,
    ExtensionState,
    HigherTimeframeBias,
    MarketEnvironment,
    MarketRegime,
    VolatilityState,
)
from apex.strategies import StrategyType, TradeDirection


class PreferredDirection(StrEnum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL =