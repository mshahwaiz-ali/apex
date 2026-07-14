from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from apex.domain.futures import RiskMode
from apex.risk import (
    ExposureState,
    ManagementPolicyType,
    RiskConfig,
    RiskDecision,
    RiskRejectionCode,
    StopQualityBand,
    analyze_phase6,
    load_risk_config,
    resolve_risk_config_for_mode,
)
from apex.scoring import (
    CandidateOutcome,
    ConflictSummary,
    DirectionalConsensus,
    Phase5AnalysisResult,
    RankedCandidate,
    ScoreBreakdown,
    ScoredCandidate,
    analyze_phase5,
)
from apex.strategies import (
    EntryMode,
    EntryZone,
    InvalidationConcept,
    InvalidationType,
    Phase4AnalysisResult,
    RawQualityMetrics,
    StrategyEvidence,
    StrategyType,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)
ORDER = tuple(StrategyType)


def _candidate(
    *,
    direction: TradeDirection = TradeDirection.LONG,
    current_price: float = 100.0,
    entry_lower: float = 99.0,
    entry_upper: float = 101.0,
    invalidation: float | None = None,
    target: float | None = None,
    extended: bool = False,
) -> TradeCandidate:
    if invalidation is None:
        invalidation = 98.0 if direction is TradeDirection.LONG else 102.0
    if target is None:
        target = 105.0 if direction is TradeDirection.LONG else 95.0
    preferred = (entry_lower + entry_upper) / 2.0
    return TradeCandidate(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=direction,
        decision_time=NOW,
        entry=EntryZone(
            lower=entry_lower,
            upper=entry_upper,
            preferred=preferred,
            current_price=current_price,
            distance_from_current=abs(current_price - preferred),
            atr_distance=abs(current_price - preferred),
            estimated_move_missed=0.0,
            location_quality=0.9,
            mode=EntryMode.MARKET_NEAR,
            rationale=("actionable entry",),
            is_extended=extended,
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=invalidation,
            rationale=("thesis invalidated",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=target,
                    label="TP1",
                    rationale=("structural target",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.9,
            structure_quality=0.9,
            entry_quality=0.9,
            momentum_quality=0.9,
            volume_quality=0.9,
            liquidity_quality=0.9,
            target_space_quality=0.9,
        ),
        evidence=StrategyEvidence(supporting=("valid deterministic thesis",)),
        metadata={},
    )


def _phase5(candidate: TradeCandidate | None = None) -> Phase5AnalysisResult:
    phase4 = Phase4AnalysisResult(
        symbol="BTC/USDT",
        decision_time=NOW,
        candidates=() if candidate is None else (candidate,),
        evaluated_strategies=ORDER,
    )
    return analyze_phase5(phase4)


def _scored(candidate_id: str, candidate: TradeCandidate)