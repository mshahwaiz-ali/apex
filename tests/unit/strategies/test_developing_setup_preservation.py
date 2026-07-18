"""Regression tests for preserving valid non-executable setup states."""

from __future__ import annotations

from types import SimpleNamespace

from apex.strategies.actionability import classify_candidate_actionability
from apex.strategies.contracts import EntryMode, TradeDirection
from apex.strategies.entry_status import EntryStatus


def _candidate(
    *,
    mode: EntryMode,
    current: float = 100.0,
    lower: float = 100.0,
    upper: float = 100.0,
    invalidation: float = 95.0,
    max_chase: float | None = 101.0,
    atr_distance: float = 0.0,
    location_quality: float = 1.0,
    extended: bool = False,
    confirmed: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        direction=TradeDirection.LONG,
        provisional=False,
        metadata={"entry_confirmation_complete": confirmed},
        invalidation=SimpleNamespace(price=invalidation),
        entry=SimpleNamespace(
            current_price=current,
            lower=lower,
            upper=upper,
            mode=mode,
            max_chase_price=max_chase,
            atr_distance=atr_distance,
            location_quality=location_quality,
            is_extended=extended,
        ),
    )


def test_unconfirmed_market_near_setup_is_preserved_as_watch() -> None:
    candidate = _candidate(mode=EntryMode.MARKET_NEAR, confirmed=False)

    assert classify_candidate_actionability(candidate) is EntryStatus.WATCH_NEAR_ENTRY


def test_confirmed_market_near_setup_is_ready_now() -> None:
    candidate = _candidate(mode=EntryMode.MARKET_NEAR, confirmed=True)

    assert classify_candidate_actionability(candidate) is EntryStatus.READY_NOW


def test_extended_retest_remains_pullback_preferred() -> None:
    candidate = _candidate(
        mode=EntryMode.RETEST,
        current=103.0,
        lower=99.5,
        upper=100.5,
        max_chase=101.0,
        atr_distance=1.8,
        location_quality=0.0,
        extended=True,
    )

    assert classify_candidate_actionability(candidate) is EntryStatus.PULLBACK_PREFERRED


def test_invalidated_setup_still_has_highest_priority() -> None:
    candidate = _candidate(
        mode=EntryMode.RETEST,
        current=94.0,
        lower=99.5,
        upper=100.5,
        invalidation=95.0,
        extended=True,
    )

    assert classify_candidate_actionability(candidate) is EntryStatus.INVALIDATED
