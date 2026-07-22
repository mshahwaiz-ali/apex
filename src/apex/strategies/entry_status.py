"""Entry actionability states for discovery-only strategy analysis."""

from enum import StrEnum


class EntryStatus(StrEnum):
    """Current actionability of a generated trade candidate."""

    READY_NOW = "READY_NOW"
    AGGRESSIVE_NOW = "AGGRESSIVE_NOW"
    PULLBACK_PREFERRED = "PULLBACK_PREFERRED"
    CONFIRMATION_AT_CMP = "CONFIRMATION_AT_CMP"
    WATCH_NEAR_ENTRY = "WATCH_NEAR_ENTRY"
    MISSED_ENTRY = "MISSED_ENTRY"
    # Compatibility name; both pipelines now serialize one canonical lifecycle state.
    LATE_OR_CHASING = "MISSED_ENTRY"
    INVALIDATED = "INVALIDATED"


ENTRY_STATUS_PRECEDENCE: tuple[EntryStatus, ...] = (
    EntryStatus.READY_NOW,
    EntryStatus.AGGRESSIVE_NOW,
    EntryStatus.PULLBACK_PREFERRED,
    EntryStatus.CONFIRMATION_AT_CMP,
    EntryStatus.WATCH_NEAR_ENTRY,
    EntryStatus.MISSED_ENTRY,
    EntryStatus.INVALIDATED,
)
