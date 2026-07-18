"""Derive shadow routing decisions from methodology strategy eligibility."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from apex.application.methodology_strategy_evaluation import (
    StrategyEligibilityEvaluation,
    StrategyEligibilityState,
)
from apex.strategies.strategy_types import StrategyType


class StrategyEnforcementAction(StrEnum):
    ALLOW = "allow"
    SUPPRESS = "suppress"
    DEFER = "defer"


@dataclass(frozen=True, slots=True)
class StrategyEnforcementDecision:
    strategy: StrategyType
    action: StrategyEnforcementAction
    reason