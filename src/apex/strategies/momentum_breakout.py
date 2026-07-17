"""Explicit momentum-breakout strategy family."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyEvidence, TradeCandidate
from apex.strategies.momentum_continuation import (
    generate_momentum_continuation_candidates,
)
from apex.strategies.strategy_types import StrategyType


def generate_momentum_breakout_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    """Return momentum candidates backed by a confirmed structural break."""

    candidates = generate_momentum_continuation_candidates(
        context,
        decision_time=decision_time,
    )
    return tuple(
        _as_momentum_breakout(candidate)
        for candidate