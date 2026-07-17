"""Entry actionability states for discovery-only strategy analysis."""

from enum import StrEnum


class EntryStatus(StrEnum):
    """Current actionability of a generated trade candidate."""

    READY_NOW = "READY_NOW"
    AGGRESSIVE_NOW = "AGGRESSIVE_NOW"
    PULLBACK_PREFERRED = "PULLBACK_PREFERRED"
    WATCH_NEAR_ENTRY = "WATCH_NEAR_ENTRY"
    LATE_OR_CHASING = "LATE_OR_CHASING"
    INVALIDATED = "INVALIDATED"


ENTRY_STATUS_PRECEDENCE: tuple[EntryStatus, ...] = (
    EntryStatus.READY_NOW,
    EntryStatus.AGGRESSIVE_NOW,
    EntryStatus.PULLBACK_PREFERRED,
    EntryStatus.WATCH_NEAR_ENTRY,
    EntryStatus.LATE_OR_CHASING,
    EntryStatus.INVALIDATED,
)
