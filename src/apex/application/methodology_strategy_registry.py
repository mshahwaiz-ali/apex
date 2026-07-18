"""Canonical methodology declarations for every Apex strategy family."""

from __future__ import annotations

from apex.application.methodology_contracts import EvidenceFamily
from apex.application.methodology_strategy_contracts import (
    ConfirmationPolicy,
    PrimaryMarketState,
    StrategyEligibility,
)
from apex.strategies.strategy_types import StrategyType

_CHAOTIC = (PrimaryMarketState.CHAOTIC,)


def