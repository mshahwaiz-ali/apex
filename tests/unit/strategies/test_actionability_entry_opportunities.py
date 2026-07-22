from __future__ import annotations

from datetime import UTC, datetime

from apex.strategies.actionability import (
    classify_candidate_actionability,
    select_actionable_entry_zone,
)
from apex.strategies.contracts import (
    EntryMode,
    EntryOpportunityHorizon,
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
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


def _zone(
    *,
    preferred: float,
    lower: float,
    upper: float,
    current: float,
    mode: EntryMode,
    atr_distance: float,
    quality: float,
    max_chase: float,
) -> EntryZone:
    return EntryZone(
        lower=lower,
        upper=upper,
        preferred=preferred,
        current_price=current,
        distance_from_current=abs(preferred - current) / current,
        atr_distance=atr_distance,
        estimated_move_missed=abs(preferred - current) / current,
        location_quality=quality,
        mode=mode,
        rationale=("test",),
        horizon=EntryOpportunityHorizon.IMMEDIATE,
        is_extended=False,
        max_chase_price=max_chase,
        expires_after_seconds=300,
    )


def _candidate(*, confirmed: bool) -> TradeCandidate:
    future = _zone(
        preferred=99.0,
        lower=98.9,
        upper=99.1,
        current=100.0,
        mode=EntryMode.PULLBACK,
        atr_distance=1.0,
        quality=0.8,
        max_chase=100.2,
    )
    market = _zone(
        preferred=100.0,
        lower=99.95,
        upper=100.05,
        current=100.0,
        mode=EntryMode.MARKET_NEAR,
        atr_distance=0.0,
        quality=1.0,
        max_chase=100.3,
    )
    return TradeCandidate(
        symbol="TEST/USDT",
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        direction=TradeDirection.LONG,
        decision_time=datetime(2026, 7, 22, tzinfo=UTC),
        entry=future,
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=98.0,
            rationale=("test",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=103.0,
                    label="primary",
                    rationale=("test",),
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
        evidence=StrategyEvidence(supporting=("test",)),
        metadata={"entry_confirmation_complete": confirmed},
        entry_opportunities=(future, market),
        provisional=False,
    )


def test_confirmed_market_opportunity_promotes_future_primary_to_ready_now() -> None:
    candidate = _candidate(confirmed=True)

    assert classify_candidate_actionability(candidate) is EntryStatus.READY_NOW
    assert select_actionable_entry_zone(candidate).mode is EntryMode.MARKET_NEAR


def test_unconfirmed_market_opportunity_remains_confirmation_at_cmp() -> None:
    candidate = _candidate(confirmed=False)

    assert classify_candidate_actionability(candidate) is EntryStatus.CONFIRMATION_AT_CMP
    assert select_actionable_entry_zone(candidate).mode is EntryMode.MARKET_NEAR
