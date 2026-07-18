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


def derive_market_state_semantics(
    methodology: MethodologySnapshot,
) -> MarketStateSemantics:
    """Describe market state and classify higher-timeframe opposition honestly."""

    market_state = methodology.market_state
    secondary = () if market_state is None else market_state.secondary
    mild = SecondaryMarketCondition.MILD_HTF_CONFLICT in secondary
    strong = SecondaryMarketCondition.STRONG_HTF_CONFLICT in secondary
    direct = SecondaryMarketCondition.DIRECT_STRUCTURAL_OPPOSITION in secondary
    blocker_codes = {item.code.value for item in methodology.hard_blockers}
    execution_blocked = bool(
        direct
        or "direct_structural_opposition" in blocker_codes
        or "wrong_strategy_for_state" in blocker_codes
    )

    if market_state is None:
        conflict_level = "unavailable"
        interpretation = (
            "canonical market-state classification is unavailable; regime fit must not be inferred"
        )
    elif direct:
        conflict_level = "direct_structural_opposition"
        interpretation = "direct structural opposition is present and prevents execution"
    elif strong:
        conflict_level = "strong"
        interpretation = (
            "strong higher-timeframe conflict is present and requires explicit strategy handling"
        )
    elif mild:
        conflict_level = "mild"
        interpretation = (
            "mild higher-timeframe conflict is visible as a quality reduction, not a hidden rejection"
        )
    else:
        conflict_level = "none"
        interpretation = "no canonical higher-timeframe conflict is recorded"

    return MarketStateSemantics(
        available=market_state is not None,
        primary_state=None if market_state is None else market_state.primary.value,
        secondary_conditions=(
            () if market_state is None else tuple(item.value for item in market_state.secondary)
        ),
        evidence_count=0 if market_state is None else len(market_state.evidence_ids),
        mild_htf_conflict=mild,
        strong_htf_conflict=strong,
        direct_structural_opposition=direct,
        conflict_level=conflict_level,
        execution_blocked_by_conflict=execution_blocked,
        interpretation=interpretation,
    )


def market_state_semantics_payload(semantics: MarketStateSemantics) -> dict[str, Any]:
    """Serialize canonical market-state interpretation."""

    return {
        "available": semantics.available,
        "primary_state": semantics.primary_state,
        "secondary_conditions": list(semantics.secondary_conditions),
        "evidence_count": semantics.evidence_count,
        "mild_htf_conflict": semantics.mild_htf_conflict,
        "strong_htf_conflict": semantics.strong_htf_conflict,
        "direct_structural_opposition": semantics.direct_structural_opposition,
        "conflict_level": semantics.conflict_level,
        "execution_blocked_by_conflict": semantics.execution_blocked_by_conflict,
        "interpretation": semantics.interpretation,
    }


__all__ = [
    "MarketStateSemantics",
    "derive_market_state_semantics",
    "market_state_semantics_payload",
]
