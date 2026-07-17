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
        if candidate.entry.max_chase_price is not None and current > candidate.entry.max_chase_price:
            return EntryStatus.LATE_OR_CHASING
    else:
        if current >= candidate.invalidation.price:
            return EntryStatus.INVALIDATED
        if candidate.entry.max_chase_price is not None and current < candidate.entry.max_chase_price:
            return EntryStatus.LATE_OR_CHASING

    if candidate.entry.lower <= current <= candidate.entry.upper:
        return EntryStatus.READY_NOW
    if candidate.entry.is_extended:
        return EntryStatus.LATE_OR_CHASING
    if (
        candidate.entry.atr_distance <= _AGGRESSIVE_MAX_ATR_DISTANCE
        and candidate.entry.location_quality >= _AGGRESSIVE_MIN_LOCATION_QUALITY
    ):
        return EntryStatus.AGGRESSIVE_NOW
    if (
        candidate.entry.mode in _PULLBACK_MODES
        and candidate.entry.atr_distance <= _PULLBACK_MAX_ATR_DISTANCE
    ):
        return EntryStatus.PULLBACK_PREFERRED
    return EntryStatus.WATCH_NEAR_ENTRY


def best_entry_status(statuses: Sequence[EntryStatus]) -> EntryStatus:
    """Return the highest-precedence status from a non-empty sequence."""

    if not statuses:
        raise ValueError("at least one entry status is required")
    return min(statuses, key=ENTRY_STATUS_PRECEDENCE.index)
