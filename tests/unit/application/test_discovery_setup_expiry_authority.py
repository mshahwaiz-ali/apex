from types import SimpleNamespace

from apex.application.discovery_setup import _setup_expiry_seconds


def _candidate(
    *,
    entry_expiry: int | None,
    lifecycle_expiry: int | None,
) -> SimpleNamespace:
    lifecycle = (
        None
        if lifecycle_expiry is None
        else SimpleNamespace(expires_after_seconds=lifecycle_expiry)
    )
    return SimpleNamespace(
        entry=SimpleNamespace(expires_after_seconds=entry_expiry),
        lifecycle=lifecycle,
    )


def test_explicit_entry_expiry_is_preserved_without_lifecycle() -> None:
    candidate = _candidate(entry_expiry=300, lifecycle_expiry=None)

    assert _setup_expiry_seconds(candidate) == 300


def test_explicit_entry_expiry_overrides_lifecycle_fallback() -> None:
    candidate = _candidate(entry_expiry=300, lifecycle_expiry=900)

    assert _setup_expiry_seconds(candidate) == 300


def test_lifecycle_expiry_is_used_when_entry_has_no_explicit_expiry() -> None:
    candidate = _candidate(entry_expiry=None, lifecycle_expiry=900)

    assert _setup_expiry_seconds(candidate) == 900


def test_missing_entry_and_lifecycle_expiry_remains_unconfigured() -> None:
    candidate = _candidate(entry_expiry=None, lifecycle_expiry=None)

    assert _setup_expiry_seconds(candidate) is None
