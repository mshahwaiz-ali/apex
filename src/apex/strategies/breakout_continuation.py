"""Deterministic breakout-continuation candidate generation."""

from __future__ import annotations

from datetime import datetime

from apex.liquidity.contracts import LiquiditySide, LiquidityZoneStatus
from apex.strategies.context import StrategyContext
from apex.strategies.contracts import (
    EntryMode,
    InvalidationConcept,
    InvalidationType,
    RawQualityMetrics,
    StrategyEvidence,
    StrategyType,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    Trade