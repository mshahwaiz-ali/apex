"""Expose canonical entry opportunities without collapsing them to one price."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_contracts import EntryOpportunity
from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class EntryOpportunitySemantics:
    """Interpret the canonical entry-opportunity set for public output."""

    opportunity_count: int
    primary_kind: str | None
    available_kinds: tuple[str, ...]
    immediate_available: bool
    aggressive_available: bool
    conditional_available: bool
    multiple_opportunities_available: bool
    interpretation: str
    opportunities: tuple[EntryOpportunity, ...]


def derive_entry_opportunity_semantics(
    methodology: MethodologySnapshot,
) -> EntryOpportunitySemantics:
    """Describe all canonical entry paths without inventing alternatives."""

    opportunities = methodology.entry_opportunities
    kinds = tuple(item.kind.value for item in opportunities)
    immediate_available = "immediate_entry" in kinds
    aggressive_available = "aggressive_entry" in kinds
    conditional_available = any(
        kind
        in {
            "preferred_nearby_entry",
            "pullback_entry",
            "retest_entry",
            "reclaim_entry",
            "rejection_entry",
            "developing_future_entry",
        }
        for kind in kinds
    )
    if not opportunities:
        interpretation = "no canonical entry opportunity is available"
    elif len(opportunities) == 1:
        interpretation = "one canonical entry opportunity is available"
    else:
        interpretation = (
            "multiple canonical entry opportunities are available and remain distinct; "
            "they must not be collapsed into one preferred price"
        )
    return EntryOpportunitySemantics(
        opportunity_count=len(opportunities),
        primary_kind=None if not opportunities else opportunities[0].kind.value,
        available_kinds=kinds,
        immediate_available=immediate_available,
        aggressive_available=aggressive_available,
        conditional_available=conditional_available,
        multiple_opportunities_available=len(opportunities) > 1,
        interpretation=interpretation,
        opportunities=opportunities,
    )


def entry_opportunity_semantics_payload(
    semantics: EntryOpportunitySemantics,
) -> dict[str, Any]:
    """Serialize entry alternatives and their independent geometry."""

    return {
        "opportunity_count": semantics.opportunity_count,
        "primary_kind": semantics.primary_kind,
        "available_kinds": list(semantics.available_kinds),
        "immediate_available": semantics.immediate_available,
        "aggressive_available": semantics.aggressive_available,
        "conditional_available": semantics.conditional_available,
        "multiple_opportunities_available": semantics.multiple_opportunities_available,
        "interpretation": semantics.interpretation,
        "opportunities": [_opportunity_payload(item) for item in semantics.opportunities],
    }


def _opportunity_payload(opportunity: EntryOpportunity) -> dict[str, Any]:
    return {
        "kind": opportunity.kind.value,
        "zone_low": opportunity.zone_low,
        "zone_high": opportunity.zone_high,
        "ideal_entry": opportunity.ideal_entry,
        "confirmation_level": opportunity.confirmation_level,
        "maximum_chase": opportunity.maximum_chase,
        "current_distance_percentage": opportunity.current_distance_percentage,
        "current_distance_atr": opportunity.current_distance_atr,
        "quality": opportunity.quality,
        "reason": opportunity.reason,
        "expiry_bars": opportunity.expiry_bars,
    }


__all__ = [
    "EntryOpportunitySemantics",
    "derive_entry_opportunity_semantics",
    "entry_opportunity_semantics_payload",
]
