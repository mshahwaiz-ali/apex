"""Regression tests for entry activation quality."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.strategies.actionability import classify_candidate_actionability
from apex.strategies.contracts import (
    EntryMode,
    EntryZone,
    InvalidationConcept,
    InvalidationType,
    RawQualityMetrics,
    StrategyEvidence,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)
from apex.strategies.entry import select_entry_zone
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


def _candidate(*, confirmed: bool, provisional: bool = False) -> TradeCandidate:
    return TradeCandidate(
        symbol="TESTUSDT",
        strategy=StrategyType.MOMENTUM_SCALP,
        direction=TradeDirection.LONG,
        decision_time=datetime(2026, 1, 1, tzinfo=UTC),
        entry=EntryZone(
            lower=100.0,
            upper=100.0,
            preferred=100.0,
            current_price=100.0,
            distance_from_current=0.0,
            atr_distance=0.0,
            estimated_move_missed=0.0,
            location_quality=1.0,
            mode=EntryMode.MARKET_NEAR,
            rationale=("test market entry",),
            max_chase_price=101.0,
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=98.0,
            rationale=("test invalidation",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=104.0,
                    label="primary",
                    rationale=("test target",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.8,
            structure_quality=0.8,
            entry_quality=0.8,
            momentum_quality=0.8,
            volume_quality=0.8,
            liquidity_quality=0.8,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(supporting=("test evidence",)),
        metadata={"entry_confirmation_complete": confirmed, "decision_atr": 2.0},
        provisional=provisional,
    )


def test_zero_width_market_entry_is_not_ready_without_confirmation() -> None:
    assert (
        classify_candidate_actionability(_candidate(confirmed=False))
        is EntryStatus.CONFIRMATION_AT_CMP
    )


def test_confirmed_closed_market_entry_can_be_ready() -> None:
    assert classify_candidate_actionability(_candidate(confirmed=True)) is EntryStatus.READY_NOW


def test_provisional_market_entry_cannot_be_ready() -> None:
    assert (
        classify_candidate_actionability(_candidate(confirmed=True, provisional=True))
        is EntryStatus.CONFIRMATION_AT_CMP
    )


def test_shared_selector_can_withhold_unconfirmed_market_entry() -> None:
    with pytest.raises(ValueError, match="no confirmed current-price entry"):
        select_entry_zone(
            current_price=100.0,
            atr=2.0,
            direction=TradeDirection.LONG,
            invalidation_price=96.0,
            target_price=108.0,
            allow_market_entry=False,
        )


@pytest.mark.parametrize(
    "mode",
    [
        EntryMode.PULLBACK,
        EntryMode.RETEST,
        EntryMode.SWEEP_RECOVERY,
        EntryMode.SCALED_ENTRY,
    ],
)
def test_cmp_inside_conditional_zone_is_not_misreported_as_nearby(
    mode: EntryMode,
) -> None:
    candidate = _candidate(confirmed=False)
    candidate = TradeCandidate(
        symbol=candidate.symbol,
        strategy=candidate.strategy,
        direction=candidate.direction,
        decision_time=candidate.decision_time,
        entry=EntryZone(
            lower=99.5,
            upper=100.5,
            preferred=100.0,
            current_price=100.0,
            distance_from_current=0.0,
            atr_distance=0.0,
            estimated_move_missed=0.0,
            location_quality=1.0,
            mode=mode,
            rationale=("current price is inside the conditional zone",),
            max_chase_price=101.0,
        ),
        invalidation=candidate.invalidation,
        targets=candidate.targets,
        quality=candidate.quality,
        evidence=candidate.evidence,
        metadata=candidate.metadata,
        provisional=candidate.provisional,
    )

    assert classify_candidate_actionability(candidate) is EntryStatus.CONFIRMATION_AT_CMP
