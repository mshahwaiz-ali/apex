"""Deterministically select one canonical entry opportunity when methodology permits."""

from __future__ import annotations

from collections.abc import Mapping

from apex.application.methodology_contracts import EntryOpportunity, EntryOpportunityType
from apex.application.methodology_selected_entry_contracts import SelectedEntryDecision
from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_strategy_contracts import SetupMaturity

_BLOCKED_MATURITIES = {
    SetupMaturity.ENTRY_MISSED,
    SetupMaturity.PATTERN_FAILED,
    SetupMaturity.INVALIDATED,
}

_PRIORITY_BY_MATURITY: Mapping[
    SetupMaturity,
    tuple[EntryOpportunityType, ...],
] = {
    SetupMaturity.PATTERN_DEVELOPING: (
        EntryOpportunityType.DEVELOPING_FUTURE,
        EntryOpportunityType.PREFERRED_NEARBY,
        EntryOpportunityType.PULLBACK,
    ),
    SetupMaturity.TRIGGER_PROVISIONAL: (
        EntryOpportunityType.AGGRESSIVE,
        EntryOpportunityType.DEVELOPING_FUTURE,
        EntryOpportunityType.PREFERRED_NEARBY,
    ),
    SetupMaturity.CONFIRMATION_PENDING_CLOSE: (
        EntryOpportunityType.RECLAIM,
        EntryOpportunityType.REJECTION,
        EntryOpportunityType.DEVELOPING_FUTURE,
    ),
    SetupMaturity.SETUP_CONFIRMED: (
        EntryOpportunityType.PREFERRED_NEARBY,
        EntryOpportunityType.PULLBACK,
        EntryOpportunityType.RETEST,
        EntryOpportunityType.RECLAIM,
        EntryOpportunityType.IMMEDIATE,
        EntryOpportunityType.AGGRESSIVE,
    ),
    SetupMaturity.RETEST_PENDING: (
        EntryOpportunityType.RETEST,
        EntryOpportunityType.PREFERRED_NEARBY,
        EntryOpportunityType.DEVELOPING_FUTURE,
    ),
    SetupMaturity.RECLAIM_PENDING: (
        EntryOpportunityType.RECLAIM,
        EntryOpportunityType.REJECTION,
        EntryOpportunityType.DEVELOPING_FUTURE,
    ),
    SetupMaturity.ENTRY_AVAILABLE: (
        EntryOpportunityType.IMMEDIATE,
        EntryOpportunityType.AGGRESSIVE,
        EntryOpportunityType.PREFERRED_NEARBY,
        EntryOpportunityType.PULLBACK,
        EntryOpportunityType.RETEST,
        EntryOpportunityType.RECLAIM,
        EntryOpportunityType.REJECTION,
    ),
    SetupMaturity.ENTRY_LATE: (
        EntryOpportunityType.PREFERRED_NEARBY,
        EntryOpportunityType.PULLBACK,
        EntryOpportunityType.RETEST,
        EntryOpportunityType.RECLAIM,
        EntryOpportunityType.DEVELOPING_FUTURE,
    ),
}


def select_canonical_entry(
    methodology: MethodologySnapshot,
) -> SelectedEntryDecision | None:
    """Choose one opportunity using maturity, quality, and distance—not tuple order.

    Selection identifies the preferred plan. It does not override hard blockers,
    setup maturity, confirmation policy, or incomplete execution geometry.
    """

    if methodology.selected_entry is not None:
        return methodology.selected_entry
    maturity = methodology.setup_maturity
    opportunities = methodology.entry_opportunities
    if maturity is None or maturity in _BLOCKED_MATURITIES or not opportunities:
        return None

    priorities = _PRIORITY_BY_MATURITY.get(maturity)
    if priorities is None:
        return None
    priority_index = {kind: index for index, kind in enumerate(priorities)}
    eligible = tuple(item for item in opportunities if item.kind in priority_index)
    if not eligible:
        return None

    ranked = sorted(
        eligible,
        key=lambda item: (
            priority_index[item.kind],
            -item.quality,
            item.current_distance_percentage,
            item.current_distance_atr,
            -item.expiry_bars,
            item.zone_low,
            item.zone_high,
            item.ideal_entry,
            item.maximum_chase,
            item.kind.value,
            item.reason,
        ),
    )
    selected = ranked[0]
    if len(ranked) > 1 and _selection_key(ranked[0], priority_index) == _selection_key(
        ranked[1], priority_index
    ):
        return None

    return SelectedEntryDecision(
        opportunity=selected,
        reason=(
            f"selected {selected.kind.value} for {maturity.value} using configured entry-type "
            "priority, then higher quality and lower current distance"
        ),
    )


def _selection_key(
    opportunity: EntryOpportunity,
    priority_index: Mapping[EntryOpportunityType, int],
) -> tuple[object, ...]:
    return (
        priority_index[opportunity.kind],
        -opportunity.quality,
        opportunity.current_distance_percentage,
        opportunity.current_distance_atr,
        -opportunity.expiry_bars,
        opportunity.zone_low,
        opportunity.zone_high,
        opportunity.ideal_entry,
        opportunity.maximum_chase,
        opportunity.kind.value,
        opportunity.reason,
    )


__all__ = ["select_canonical_entry"]
