"""Canonical authority for candidate-selected entry and trigger geometry."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from apex.strategies.contracts import EntryZone

_METADATA_VALUE = str | int | float | bool


@dataclass(frozen=True, slots=True)
class CandidateEntryAuthority:
    """Preserve one selected entry while keeping a distinct activation trigger."""

    selected_entry: float
    trigger_level: float
    geometry_owner: str
    trigger_matches_selected_entry: bool

    def __post_init__(self) -> None:
        for name, value in (
            ("selected entry", self.selected_entry),
            ("trigger level", self.trigger_level),
        ):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        if not self.geometry_owner.strip():
            raise ValueError("geometry owner cannot be empty")


def resolve_candidate_entry_authority(
    entry: EntryZone,
    metadata: Mapping[str, _METADATA_VALUE],
) -> CandidateEntryAuthority:
    """Resolve selected-entry and trigger authority without substituting CMP."""

    owner_value = metadata.get("entry_geometry_owner")
    geometry_owner = (
        owner_value.strip()
        if isinstance(owner_value, str) and owner_value.strip()
        else "candidate_entry_zone"
    )

    trigger_value = metadata.get("retest_trigger_level")
    if trigger_value is None:
        trigger_level = entry.preferred
    elif isinstance(trigger_value, bool) or not isinstance(trigger_value, int | float):
        raise ValueError("explicit retest trigger level must be numeric")
    else:
        trigger_level = float(trigger_value)
        if not math.isfinite(trigger_level) or trigger_level <= 0:
            raise ValueError("explicit retest trigger level must be positive and finite")
        if not entry.lower <= trigger_level <= entry.upper:
            raise ValueError("explicit retest trigger level must lie inside the entry zone")

    return CandidateEntryAuthority(
        selected_entry=entry.preferred,
        trigger_level=trigger_level,
        geometry_owner=geometry_owner,
        trigger_matches_selected_entry=math.isclose(
            trigger_level,
            entry.preferred,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ),
    )


__all__ = [
    "CandidateEntryAuthority",
    "resolve_candidate_entry_authority",
]
