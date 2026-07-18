"""Evaluate strategy eligibility against canonical methodology state and evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from apex.application.methodology_contracts import EvidenceFamily, EvidenceObservation
from apex.application.methodology_strategy_contracts import PrimaryMarketState
from apex.application.methodology_strategy_registry import strategy_eligibility
from apex.strategies.strategy_types import StrategyType


class StrategyEligibilityState(StrEnum):
    COMPATIBLE = "compatible