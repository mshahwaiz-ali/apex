"""Explicit liquidity-rejection reversal strategy family."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyEvidence, TradeCandidate
from apex.strategies.liquidity_reversal import generate_liquidity_reversal_candidates
from apex.strategies.strategy_types import StrategyType


def generate_liquidity_rejection_reversal_candidates(
    context: StrategyContext,
    *,