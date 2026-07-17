"""Explicit compression-expansion strategy family."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apex.strategies.breakout_continuation import (
    generate_breakout_continuation_candidates,
)
from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyEvidence, TradeCandidate
from apex.strategies.strategy_types import StrategyType
from apex.structure.regime import MarketRegime