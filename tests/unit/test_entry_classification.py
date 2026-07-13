"""Tests for canonical direction-aware entry-state classification."""

import pytest
from pydantic import ValidationError

from apex.domain import (
    EntryClassificationInput,
    EntryState,
    FuturesDirection,
    classify_entry_state,
)


def _long(**overrides: object) -> EntryClassificationInput:
    data: dict[str, object] = {
        "direction": FuturesDirection.LONG,
        "current_price": 100.5,
        "zone_low": 100.0,
        "zone_high": 101.0,
        "ideal_entry": 100.5,
        "maximum_chase_price": 102.0,
        "reclaim_trigger": 99.0,
        "retest_trigger": 101.25,
        "structural_invalidation": 98.0,
    }
    data.update(overrides)
    return EntryClassificationInput.model_validate(data)


def _short(**overrides: object) -> EntryClassificationInput:
    data: dict[str, object] = {
        "direction": FuturesDirection.SHORT,
        "current_price": 100.5,
        "zone_low": 100.0,
        "zone_high": 101.0,
        "ideal_entry": 100.5,
        "maximum_chase_price": 99.0,
        "reclaim_trigger": 102.0,
        "retest_trigger": 99.75,
        "structural_invalidation": 103.0,
    }
    data.update(overrides)
    return EntryClassificationInput.model_validate(data)


@pytest.mark.parametrize(
    ("case_id", "geometry", "expected"),
    [
        ("long_lower_boundary", _long(current_price=100.0), EntryState.READY_NOW),
        ("long_upper_boundary", _long(current_price=101.0), EntryState.READY_NOW),
        ("long_step_below_zone", _long(current_price=99.5), EntryState.APPROACHING_ENTRY),
        ("long_reclaim_boundary", _long(current_price=99.0), EntryState.WAIT_FOR_RECLAIM),
        ("long_retest_boundary", _long(current_price=101.25), EntryState.WAIT_FOR_RETEST),
        ("long_chase_boundary", _long(current_price=102.0), EntryState.WAIT_FOR_RETEST),
        ("long_beyond_chase", _long(current_price=102.01), EntryState.MISSED_ENTRY),
        ("long_invalidation_boundary", _long(current_price=98.0), EntryState.INVALIDATED),
        ("long_before_invalidation", _long(current_price=98.01), EntryState.WAIT_FOR_RECLAIM),
        (
            "long_missing_reclaim",
            _long(current_price=99.0, reclaim_trigger=None),
            EntryState.APPROACHING_ENTRY,
        ),
        ("short_lower_boundary", _short(current_price=100.0), EntryState.READY_NOW),
        ("short_upper_boundary", _short(current_price=101.0), EntryState.READY_NOW),
        ("short_step_above_zone", _short(current_price=101.5), EntryState.APPROACHING_ENTRY),
        ("short_reclaim_boundary", _short(current_price=102.0), EntryState.WAIT_FOR_RECLAIM),
        ("short_retest_boundary", _short(current_price=99.75), EntryState.WAIT_FOR_RETEST),
        ("short_chase_boundary", _short(current_price=99.0), EntryState.WAIT_FOR_RETEST),
        ("short_beyond_chase", _short(current_price=98.99), EntryState.MISSED_ENTRY),
        ("short_invalidation_boundary", _short(current_price=103.0), EntryState.INVALIDATED),
        ("short_before_invalidation", _short(current_price=102.99), EntryState.WAIT_FOR_RECLAIM),
        (
            "short_missing_reclaim",
            _short(current_price=102.0, reclaim_trigger=None),
            EntryState.APPROACHING_ENTRY,
        ),
        ("rejected_setup", _long(setup_eligible=False), EntryState.NO_TRADE),
        ("incomplete_geometry", _long(geometry_complete=False), EntryState.NO_TRADE),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_entry_classification_boundaries(
    case_id: str,
    geometry: EntryClassificationInput,
    expected: EntryState,
) -> None:
    assert case_id
    assert classify_entry_state(geometry).state is expected


def test_entry_classification_precedence_invalidated_before_ready_now() -> None:
    geometry = _long(current_price=100.5, structural_invalidation=101.0)

    assert classify_entry_state(geometry).state is EntryState.INVALIDATED


def test_entry_classification_precedence_missed_before_retest() -> None:
    geometry = _short(current_price=98.0, maximum_chase_price=99.0, retest_trigger=98.5)

    assert classify_entry_state(geometry).state is EntryState.MISSED_ENTRY


def test_entry_classification_watch_when_valid_but_not_actionable() -> None:
    geometry = _long(current_price=103.0, maximum_chase_price=104.0, retest_trigger=104.5)

    assert classify_entry_state(geometry).state is EntryState.WATCH


@pytest.mark.parametrize(
    ("case_id", "overrides", "match"),
    [
        ("malformed_zone", {"zone_low": 101.0, "zone_high": 100.0}, "entry zone low"),
        ("non_finite_price", {"current_price": float("inf")}, "current_price must be finite"),
        ("bad_long_chase", {"maximum_chase_price": 100.5}, "long maximum chase"),
    ],
)
def test_entry_classification_rejects_malformed_geometry(
    case_id: str,
    overrides: dict[str, object],
    match: str,
) -> None:
    assert case_id
    with pytest.raises(ValidationError, match=match):
        _long(**overrides)
