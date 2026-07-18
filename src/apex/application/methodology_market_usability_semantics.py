"""Interpret canonical market usability without treating it as trade confidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.market_usability import MarketUsabilityState
from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class MarketUsabilitySemantics:
    """Public interpretation of market-data and execution-quality usability."""

    available: bool
    state: str | None
    score