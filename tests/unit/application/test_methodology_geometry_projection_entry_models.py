from __future__ import annotations

import pytest

from apex.application.methodology_geometry_projection import _entry_model
from apex.strategies.entry_status import EntryStatus


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (EntryStatus.READY_NOW, "immediate_entry"),
        (EntryStatus.AGGRESSIVE_NOW, "aggressive_entry"),
        (EntryStatus.PULLBACK_PREFERRED, "pullback_entry"),
        (EntryStatus.CONFIRMATION_AT_CMP, "confirmation_entry"),
        (EntryStatus.WATCH_NEAR_ENTRY, "developing_future_entry"),
        (EntryStatus.LATE_OR_CHASING, "preferred_nearby_entry"),
        (EntryStatus.INVALIDATED, "developing_future_entry"),
    ],
)
def test_every_entry_status_has_a_public_geometry_model(
    status: EntryStatus,
    expected: str,
) -> None:
    assert _entry_model(status) == expected


def test_entry_model_mapping_covers_the_complete_enum() -> None:
    assert {_entry_model(status) for status in EntryStatus} == {
        "immediate_entry",
        "aggressive_entry",
        "pullback_entry",
        "confirmation_entry",
        "developing_future_entry",
        "preferred_nearby_entry",
    }
