"""Interpret selected-entry decisions without treating tuple order as authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_contracts import EntryOpportunity, EntryOpportunityType
from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_strategy_contracts import SetupMaturity


_IMMEDIATE_TYPES = {
    EntryOpportunityType.IMMEDIATE,
    EntryOpportunityType.AGGRESSIVE,
}
_CONDITIONAL_TYPES = {
    EntryOpportunityType.PREFERRED_NEARBY,
    EntryOpportunityType.PULLBACK,
    EntryOpportunityType.RETEST,
    EntryOpportunityType.RECLAIM,
    EntryOpportunityType.REJECTION,
    EntryOpportunityType.DEVELOPING_FUTURE,
}


@dataclass(frozen=True, slots=True)
class SelectedEntrySemantics:
    """Public interpretation of canonical entry selection and executability."""

    opportunity_count: int
    selection_available: bool
    selection_authoritative: bool
    selected_index: int | None
    selected_kind: str | None
    selected_opportunity: dict[str, Any] | None
    currently_executable: bool
    future_trigger_required: bool
    required_trigger: float | None
    aggressive_alternative_available: bool
    conditional_alternative_available: bool
    better_nearby_alternative_available: bool
    maximum_chase_respected: bool | None
    selection_reason: str
    selection_limitations: tuple[str, ...]


def derive_selected_entry_semantics(
    methodology: MethodologySnapshot,
) -> SelectedEntrySemantics:
    """Select only an unambiguous canonical opportunity; otherwise stay unavailable."""

    opportunities = methodology.entry_opportunities
    selected = opportunities[0] if len(opportunities) == 1 else None
    maturity = methodology.setup_maturity
    currently_executable = bool(
        selected is not None
        and selected.kind in _IMMEDIATE_TYPES
        and maturity is SetupMaturity.ENTRY_AVAILABLE
        and methodology.executable
    )
    future_trigger_required = bool(
        selected is not None
        and selected.kind in _CONDITIONAL_TYPES
        and not currently_executable
    )
    aggressive_available = any(
        item.kind is EntryOpportunityType.AGGRESSIVE for item in opportunities
    )
    conditional_available = any(item.kind in _CONDITIONAL_TYPES for item in opportunities)
    better_nearby = any(
        item.kind is EntryOpportunityType.PREFERRED_NEARBY for item in opportunities
    )

    if not opportunities:
        reason = "no canonical entry opportunity exists"
    elif len(opportunities) > 1:
        reason = (
            "multiple canonical opportunities exist, but no explicit selected-opportunity field "
            "is available; tuple order is not treated as authority"
        )
    elif methodology.hard_blockers:
        reason = "one canonical opportunity exists, but methodology hard blockers prevent execution"
    elif currently_executable:
        reason = "the only canonical opportunity is immediate and methodology-executable"
    elif future_trigger_required:
        reason = "the only canonical opportunity is conditional and requires its trigger"
    else:
        reason = "the only canonical opportunity is visible, but current execution is not proven"

    return SelectedEntrySemantics(
        opportunity_count=len(opportunities),
        selection_available=selected is not None,
        selection_authoritative=False,
        selected_index=0 if selected is not None else None,
        selected_kind=None if selected is None else selected.kind.value,
        selected_opportunity=None if selected is None else _opportunity_payload(selected),
        currently_executable=currently_executable,
        future_trigger_required=future_trigger_required,
        required_trigger=(
            None if selected is None else selected.confirmation_level
        ),
        aggressive_alternative_available=aggressive_available,
        conditional_alternative_available=conditional_available,
        better_nearby_alternative_available=better_nearby,
        maximum_chase_respected=None,
        selection_reason=reason,
        selection_limitations=(
            "the canonical snapshot does not expose an explicit selected-opportunity identifier",
            "multiple opportunities must not be reduced to the first tuple item",
            "current-price and direction geometry are unavailable for independent chase validation",
            "entry selection cannot override hard blockers, maturity, or incomplete methodology geometry",
        ),
    )


def selected_entry_semantics_payload(
    semantics: SelectedEntrySemantics,
) -> dict[str, Any]:
    """Serialize selected-entry interpretation."""

    return {
        "opportunity_count": semantics.opportunity_count,
        "selection_available": semantics.selection_available,
        "selection_authoritative": semantics.selection_authoritative,
        "selected_index": semantics.selected_index,
        "selected_kind": semantics.selected_kind,
        "selected_opportunity": semantics.selected_opportunity,
        "currently_executable": semantics.currently_executable,
        "future_trigger_required": semantics.future_trigger_required,
        "required_trigger": semantics.required_trigger,
        "aggressive_alternative_available": semantics.aggressive_alternative_available,
        "conditional_alternative_available": semantics.conditional_alternative_available,
        "better_nearby_alternative_available": semantics.better_nearby_alternative_available,
        "maximum_chase_respected": semantics.maximum_chase_respected,
        "selection_reason": semantics.selection_reason,
        "selection_limitations": list(semantics.selection_limitations),
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
    "SelectedEntrySemantics",
    "derive_selected_entry_semantics",
    "selected_entry_semantics_payload",
]
