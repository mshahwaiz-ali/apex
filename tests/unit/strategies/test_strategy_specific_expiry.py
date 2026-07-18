from __future__ import annotations

from datetime import UTC, datetime

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
    candidate_expiry_seconds,
)
from apex.strategies.strategy_types import StrategyType


def _entry(mode: EntryMode) -> EntryZone:
    return EntryZone(
        lower=99.5,
        upper=100.5,
        preferred=100.0,
        current_price=100.0,
        distance_from_current=0.0,
        atr_distance=0.0,
        estimated_move_missed=0.0,
        location_quality=0.8,
        mode=mode,
        rationale=("test entry",),
    )


def _candidate(strategy: StrategyType, mode: EntryMode) -> TradeCandidate:
    return TradeCandidate(
        symbol="TEST/USDT",
        strategy=strategy,
        direction=TradeDirection.LONG,
        decision_time=datetime(2026, 1, 1, tzinfo=UTC),
        entry=_entry(mode),
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
        metadata={},
    )


def test_scalp_market_entry_expires_before_structural_retest() -> None:
    scalp = candidate_expiry_seconds(
        strategy=StrategyType.MOMENTUM_SCALP,
        entry_mode=EntryMode.MARKET_NEAR,
    )
    retest = candidate_expiry_seconds(
        strategy=StrategyType.BREAKOUT_RETEST,
        entry_mode=EntryMode.RETEST,
    )

    assert scalp == 180
    assert retest == 4_050
    assert scalp < retest


def test_pullback_entry_lasts_longer_than_market_entry_for_same_strategy() -> None:
    market = candidate_expiry_seconds(
        strategy=StrategyType.TREND_PULLBACK,
        entry_mode=EntryMode.MARKET_NEAR,
    )
    pullback = candidate_expiry_seconds(
        strategy=StrategyType.TREND_PULLBACK,
        entry_mode=EntryMode.PULLBACK,
    )

    assert market == 1_800
    assert pullback == 4_500


def test_trade_candidate_uses_strategy_specific_expiry_by_default() -> None:
    candidate = _candidate(StrategyType.BREAKOUT_RETEST, EntryMode.RETEST)

    assert candidate.lifecycle is not None
    assert candidate.lifecycle.expires_after_seconds == 4_050


def test_explicit_entry_expiry_remains_authoritative() -> None:
    entry = _entry(EntryMode.RETEST)
    explicit = EntryZone(
        lower=entry.lower,
        upper=entry.upper,
        preferred=entry.preferred,
        current_price=entry.current_price,
        distance_from_current=entry.distance_from_current,
        atr_distance=entry.atr_distance,
        estimated_move_missed=entry.estimated_move_missed,
        location_quality=entry.location_quality,
        mode=entry.mode,
        rationale=entry.rationale,
        expires_after_seconds=777,
    )
    candidate = _candidate(StrategyType.BREAKOUT_RETEST, EntryMode.RETEST)
    overridden = TradeCandidate(
        symbol=candidate.symbol,
        strategy=candidate.strategy,
        direction=candidate.direction,
        decision_time=candidate.decision_time,
        entry=explicit,
        invalidation=candidate.invalidation,
        targets=candidate.targets,
        quality=candidate.quality,
        evidence=candidate.evidence,
        metadata=candidate.metadata,
    )

    assert overridden.lifecycle is not None
    assert overridden.lifecycle.expires_after_seconds == 777
