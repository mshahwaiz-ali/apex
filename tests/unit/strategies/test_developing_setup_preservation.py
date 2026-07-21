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
    aggressive_permitted: bool = False,
    provisional: bool = False,
    confirmation_basis: str = "closed_evidence",
) -> SimpleNamespace:
    return SimpleNamespace(
        direction=TradeDirection.LONG,
        provisional=provisional,
        metadata={
            "entry_confirmation_complete": confirmed,
            "aggressive_entry_permitted": aggressive_permitted,
            "confirmation_basis": confirmation_basis,
        },
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


def test_unconfirmed_market_near_setup_requires_confirmation_at_cmp() -> None:
    candidate = _candidate(mode=EntryMode.MARKET_NEAR, confirmed=False)

    assert classify_candidate_actionability(candidate) is EntryStatus.CONFIRMATION_AT_CMP


def test_confirmed_market_near_setup_is_ready_now() -> None:
    candidate = _candidate(mode=EntryMode.MARKET_NEAR, confirmed=True)

    assert classify_candidate_actionability(candidate) is EntryStatus.READY_NOW


def test_extended_retest_is_late_even_when_wider_setup_remains_alive() -> None:
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

    assert classify_candidate_actionability(candidate) is EntryStatus.LATE_OR_CHASING


def test_aggressive_entry_requires_explicit_strategy_permission() -> None:
    candidate = _candidate(
        mode=EntryMode.MOMENTUM_CONTINUATION,
        current=100.2,
        lower=99.8,
        upper=100.0,
        max_chase=101.0,
        atr_distance=0.2,
        location_quality=0.9,
        confirmed=True,
    )

    assert classify_candidate_actionability(candidate) is EntryStatus.WATCH_NEAR_ENTRY


def test_confirmed_non_provisional_strategy_can_explicitly_allow_aggressive_entry() -> None:
    candidate = _candidate(
        mode=EntryMode.MOMENTUM_CONTINUATION,
        current=100.2,
        lower=99.8,
        upper=100.0,
        max_chase=101.0,
        atr_distance=0.2,
        location_quality=0.9,
        confirmed=True,
        aggressive_permitted=True,
    )

    assert classify_candidate_actionability(candidate) is EntryStatus.AGGRESSIVE_NOW


def test_provisional_or_mandatory_close_evidence_blocks_aggressive_entry() -> None:
    assert (
        classify_candidate_actionability(
            _candidate(
                mode=EntryMode.MOMENTUM_CONTINUATION,
                current=100.2,
                lower=99.8,
                upper=100.0,
                max_chase=101.0,
                atr_distance=0.2,
                location_quality=0.9,
                confirmed=True,
                aggressive_permitted=True,
                provisional=True,
            )
        )
        is EntryStatus.WATCH_NEAR_ENTRY
    )
    assert (
        classify_candidate_actionability(
            _candidate(
                mode=EntryMode.MOMENTUM_CONTINUATION,
                current=100.2,
                lower=99.8,
                upper=100.0,
                max_chase=101.0,
                atr_distance=0.2,
                location_quality=0.9,
                confirmed=True,
                aggressive_permitted=True,
                confirmation_basis="mandatory_close",
            )
        )
        is EntryStatus.WATCH_NEAR_ENTRY
    )


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
