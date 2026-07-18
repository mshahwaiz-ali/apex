"""Interpret canonical market state and higher-timeframe conflict transparently."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_strategy_contracts import SecondaryMarketCondition


@dataclass(frozen=True, slots=True)
class MarketStateSemantics:
    """Public interpretation of canonical market-state classification."""

    available: bool
    primary_state: str | None
    secondary_conditions: tuple[str, ...]
    evidence_count: int
    mild_htf_conflict: bool
    strong_htf_conflict: bool
    direct_structural_opposition: bool
    conflict_level: str
    execution_blocked_by_conflict: bool
    interpretation: str


def derive_market_state_semantics