from __future__ import annotations

import pytest

from apex.scoring.selection import is_entry_status_executable
from apex.strategies.entry_status import EntryStatus


@pytest.mark.parametrize(
    "status",
    [
        EntryStatus.READY_NOW,
        EntryStatus.AGGRESSIVE_NOW,
    ],
)
def test_current_execution_states_are_executable(status: EntryStatus) -> None:
    assert is_entry_status_executable(status)


@pytest.mark.parametrize(
    "status",
    [
        EntryStatus.PULLBACK_PREFERRED,
        EntryStatus.WATCH_NEAR_ENTRY,
        EntryStatus.LATE_OR_CHASING,
        EntryStatus.INVALIDATED,
    ],
)
def test_developing_or_invalid_states_are_not_executable(status: EntryStatus) -> None:
    assert not is_entry_status_executable(status)
