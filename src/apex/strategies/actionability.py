"""Deterministic discovery-only candidate actionability classification."""

from __future__ import annotations

from collections.abc import Sequence

from apex.strategies.contracts import EntryMode, EntryZone, TradeCandidate, TradeDirection
from apex.strategies.entry_status import ENTRY_STATUS_PRECEDENCE, EntryStatus

_AGGRESSIVE_MAX_ATR_DISTANCE = 0.35
_AGGRESSIVE_MIN_LOCATION_QUALITY = 0.60
_PULLBACK_MAX_ATR_DISTANCE = 1.50
_PULLBACK_MODES = {
    EntryMode.PULLBACK,
    EntryMode.RETEST,
    EntryMode.SWEEP_RECOVERY,
    EntryMode.SCALED_ENTRY,
}


def classify_candidate_actionability(candidate: TradeCandidate) -> EntryStatus:
    """Classify one generated candidate using every preserved entry opportunity."""

    current = candidate.entry.current_price
    if candidate.direction is TradeDirection.LONG:
        if current <= candidate.invalidation.price:
            return EntryStatus.INVALIDATED
    elif current >= candidate.invalidation.price:
        return EntryStatus.INVALIDATED

    confirmed = (
        candidate.metadata.get("entry_confirmation_complete") is True and not candidate.provisional
    )
    opportunities = candidate.entry_opportunities or (candidate.entry,)

    # ``find_entry_zones`` ranks by reward geometry, so a future pullback can be
    # the candidate's primary entry even while a separately preserved market
    # zone is valid at CMP. Do not let that ranking choice hide a confirmed
    # executable opportunity.
    cmp_entries = tuple(zone for zone in opportunities if zone.lower <= current <= zone.upper)
    if cmp_entries:
        return EntryStatus.READY_NOW if confirmed else EntryStatus.CONFIRMATION_AT_CMP

    if (
        candidate.metadata.get("aggressive_entry_permitted") is True
        and confirmed
        and candidate.metadata.get("confirmation_basis") != "mandatory_close"
        and any(_aggressive_zone_is_eligible(zone) for zone in opportunities)
    ):
        return EntryStatus.AGGRESSIVE_NOW

    # A structurally valid setup must remain discoverable even when CMP has
    # already moved beyond an advisory chase boundary. The entry zone, stop,
    # targets, and structural invalidation are the canonical trade plan; status
    # labels must not delete that plan before price has actually invalidated it.
    primary = candidate.entry
    if primary.mode in _PULLBACK_MODES and primary.atr_distance <= _PULLBACK_MAX_ATR_DISTANCE:
        return EntryStatus.PULLBACK_PREFERRED
    return EntryStatus.WATCH_NEAR_ENTRY


def select_actionable_entry_zone(
    candidate: TradeCandidate,
    *,
    status: EntryStatus | None = None,
) -> EntryZone:
    """Return the entry zone that truthfully supports the classified actionability."""

    resolved_status = classify_candidate_actionability(candidate) if status is None else status
    opportunities = candidate.entry_opportunities or (candidate.entry,)
    current = candidate.entry.current_price

    if resolved_status in {EntryStatus.READY_NOW, EntryStatus.CONFIRMATION_AT_CMP}:
        cmp_entries = tuple(zone for zone in opportunities if zone.lower <= current <= zone.upper)
        if cmp_entries:
            return min(
                cmp_entries,
                key=lambda zone: (
                    zone.mode is not EntryMode.MARKET_NEAR,
                    abs(zone.preferred - current),
                    -zone.location_quality,
                    zone.preferred,
                ),
            )

    if resolved_status is EntryStatus.AGGRESSIVE_NOW:
        aggressive_entries = tuple(
            zone for zone in opportunities if _aggressive_zone_is_eligible(zone)
        )
        if aggressive_entries:
            return min(
                aggressive_entries,
                key=lambda zone: (
                    zone.atr_distance,
                    -zone.location_quality,
                    abs(zone.preferred - current),
                    zone.preferred,
                ),
            )

    return candidate.entry


def _aggressive_zone_is_eligible(zone: EntryZone) -> bool:
    return (
        zone.atr_distance <= _AGGRESSIVE_MAX_ATR_DISTANCE
        and zone.location_quality >= _AGGRESSIVE_MIN_LOCATION_QUALITY
        and not zone.is_extended
    )


def best_entry_status(statuses: Sequence[EntryStatus]) -> EntryStatus:
    """Return the highest-precedence status from a non-empty sequence."""

    if not statuses:
        raise ValueError("at least one entry status is required")
    return min(statuses, key=ENTRY_STATUS_PRECEDENCE.index)
