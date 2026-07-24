from apex.application.discovery_setup import _execution_allowed_now
from apex.strategies.entry_status import EntryStatus


def test_confirmation_required_entry_is_not_immediately_executable_when_incomplete() -> None:
    assert not _execution_allowed_now(
        EntryStatus.READY_NOW,
        confirmation_required=True,
        confirmation_complete=False,
    )


def test_confirmation_required_entry_is_executable_after_confirmation() -> None:
    assert _execution_allowed_now(
        EntryStatus.READY_NOW,
        confirmation_required=True,
        confirmation_complete=True,
    )


def test_non_confirmation_entry_preserves_existing_execution_authority() -> None:
    assert _execution_allowed_now(
        EntryStatus.READY_NOW,
        confirmation_required=False,
        confirmation_complete=False,
    )


def test_non_executable_entry_status_remains_non_executable() -> None:
    assert not _execution_allowed_now(
        EntryStatus.WATCH_NEAR_ENTRY,
        confirmation_required=False,
        confirmation_complete=True,
    )
