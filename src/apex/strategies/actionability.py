"""Deterministic discovery-only candidate actionability classification."""

from __future__ import annotations

from collections.abc import Sequence

from apex.strategies.contracts import EntryMode, TradeCandidate, TradeDirection
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
    """Classify one generated candidate using current-price geometry."""

    current = candidate.entry.current_price
    if candidate.direction is TradeDirection.LONG:
        if current <= candidate.invalidation.price:
            return EntryStatus.INVALIDATED
        beyond_chase = (
            candidate.entry.max_chase_price is not None
            and current > candidate.entry.max_chase_price
        )
    else:
        if current >= candidate.invalidation.price:
            return EntryStatus.INVALIDATED
        beyond_chase = (
            candidate.entry.max_chase_price is not None
            and current < candidate.entry.max_chase_price
        )

    if candidate.entry.lower <= current <= candidate.entry.upper:
        confirmed = (
            candidate.metadata.get("entry_confirmation_complete") is True
            and not candidate.provisional
        )
        if confirmed:
            return EntryStatus.READY_NOW
        return EntryStatus.CONFIRMATION_AT_CMP
    # Current execution geometry takes precedence over the fact that the wider
    # setup may remain structurally alive.  A future pullback opportunity is
    # preserved in ``entry_opportunities``; it must not hide a missed primary
    # entry or authorize a chase.
    if candidate.entry.is_extended or beyond_chase:
        return EntryStatus.MISSED_ENTRY
    if (
        candidate.entry.mode in _PULLBACK_MODES
        and candidate.entry.atr_distance <= _PULLBACK_MAX_ATR_DISTANCE
    ):
        return EntryStatus.PULLBACK_PREFERRED
    confirmed = (
        candidate.metadata.get("entry_confirmation_complete") is True and not candidate.provisional
    )
    if (
        candidate.metadata.get("aggressive_entry_permitted") is True
        and confirmed
        and candidate.metadata.get("confirmation_basis") != "mandatory_close"
        and candidate.entry.atr_distance <= _AGGRESSIVE_MAX_ATR_DISTANCE
        and candidate.entry.location_quality >= _AGGRESSIVE_MIN_LOCATION_QUALITY
    ):
        return EntryStatus.AGGRESSIVE_NOW
    return EntryStatus.WATCH_NEAR_ENTRY


def best_entry_status(statuses: Sequence[EntryStatus]) -> EntryStatus:
    """Return the highest-precedence status from a non-empty sequence."""

    if not statuses:
        raise ValueError("at least one entry status is required")
    return min(statuses, key=ENTRY_STATUS_PRECEDENCE.index)
