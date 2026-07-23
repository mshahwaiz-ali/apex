"""Deterministic timeframe authority for breakout continuation and retest routing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.strategies.context import StrategyContext, TimeframeContext, TimeframeRole
from apex.strategies.contracts import TradeCandidate, TradeDirection
from apex.strategies.strategy_types import StrategyType
from apex.structure.contracts import TrendDirection


class Alignment(StrEnum):
    """Directional relationship between one timeframe and a candidate