"""Summarize methodology enforcement for the selected discovery strategy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from apex.application.methodology_strategy_enforcement import (
    StrategyEnforcementAction,
    StrategyEnforcementDecision,
)
from apex.strategies.strategy_types import StrategyType


class SelectedStrategyVerdictState(StrEnum):
    NO_SETUP