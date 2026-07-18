"""Canonical selected-entry decision for methodology snapshots."""

from __future__ import annotations

from dataclasses import dataclass

from apex.application.methodology_contracts import EntryOpportunity


@dataclass(frozen=True, slots=True)
class SelectedEntryDecision:
    """Explicitly identify the opportunity selected by the methodology core.

    The decision references the complete immutable opportunity instead of a tuple
    index. Snapshot validation