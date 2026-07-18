"""Canonical selected-entry decision for methodology snapshots."""

from __future__ import annotations

from dataclasses import dataclass

from apex.application.methodology_contracts import EntryOpportunity


@dataclass(frozen=True, slots=True)
class SelectedEntryDecision:
    """Explicitly identify the opportunity selected by the methodology core.

    The decision references the complete immutable opportunity instead of a tuple
    index. Snapshot validation ensures that the referenced opportunity is present
    in the canonical opportunity set, so tuple order never becomes authority.
    """

    opportunity: EntryOpportunity
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("selected-entry decision reason cannot be empty")


__all__ = ["SelectedEntryDecision"]
