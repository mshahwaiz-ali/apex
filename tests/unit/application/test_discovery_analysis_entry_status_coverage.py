from __future__ import annotations

import pytest

from apex.application.discovery_analysis import _entry_kind, _entry_quality, _expiry_bars
from apex.application.methodology_contracts import EntryOpportunityType
from apex.strategies.entry_status import EntryStatus


@pytest.mark.parametrize("status", tuple(EntryStatus))
def test_entry_snapshot_helpers_cover_every_canonical_status(status: EntryStatus) -> None:
    assert isinstance(_entry_kind(status), EntryOpportunityType)
    assert 0.0 <= _entry_quality(status) <= 1.0
    assert _expiry_bars(status) > 0


def test_confirmation_at_cmp_has_explicit_snapshot_quality() -> None:
    assert _entry_kind(EntryStatus.CONFIRMATION_AT_CMP) is EntryOpportunityType.DEVELOPING_FUTURE
    assert _entry_quality(EntryStatus.CONFIRMATION_AT_CMP) == 0.65
    assert _expiry_bars(EntryStatus.CONFIRMATION_AT_CMP) == 2


def test_missed_entry_alias_retains_existing_snapshot_semantics() -> None:
    assert EntryStatus.LATE_OR_CHASING is EntryStatus.MISSED_ENTRY
    assert _entry_kind(EntryStatus.MISSED_ENTRY) is EntryOpportunityType.RETEST
    assert _entry_quality(EntryStatus.MISSED_ENTRY) == 0.25
    assert _expiry_bars(EntryStatus.MISSED_ENTRY) == 2
