from __future__ import annotations

from datetime import UTC, datetime

from apex.domain.methodology_contracts import (
    ContextState,
    ExecutionState,
    LayeredStateSnapshot,
    ScoreDimensions,
    SetupState,
)
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
from apex.strategies.strategy_types import StrategyType


def _candidate(**overrides: object) -> TradeCandidate:
    values: dict[str, object] = {
        "symbol": "BTC/USDT",
        "strategy": StrategyType.TREND_PULLBACK,
        "direction": TradeDirection.LONG,
        "decision_time": datetime(2026, 7, 21, tzinfo=UTC),
        "entry": EntryZone(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=100.0,
            distance_from_current=0.0,
            atr_distance=0.0,
            estimated_move_missed=0.0,
            location_quality=0.8,
            mode=EntryMode.MARKET_NEAR,
            rationale=("test entry",),
        ),
        "invalidation": InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=95.0,
            rationale=("test invalidation",),
        ),
        "targets": TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=110.0,
                    label="TP1",
                    rationale=("test target",),
                ),
            )
        ),
        "quality": RawQualityMetrics(
            trend_alignment=0.8,
            structure_quality=0.8,
            entry_quality=0.8,
            momentum_quality=0.8,
            volume_quality=0.8,
            liquidity_quality=0.8,
            target_space_quality=0.8,
        ),
        "evidence": StrategyEvidence(supporting=("test evidence",)),
        "metadata": {"entry_confirmation_complete": True},
    }
    values.update(overrides)
    return TradeCandidate(**values)  # type: ignore[arg-type]


def test_candidate_defaults_preserve_legacy_construction() -> None:
    candidate = _candidate()

    assert candidate.layered_state == LayeredStateSnapshot()
    assert candidate.score_dimensions == ScoreDimensions()


def test_candidate_accepts_layered_state_without_affecting_raw_quality() -> None:
    layered_state = LayeredStateSnapshot(
        execution_state=ExecutionState.CLEAN,
        setup_state=SetupState.PULLBACK,
        context_state=ContextState.TRENDING_UP,
    )
    scores = ScoreDimensions(
        pattern_confidence=76.0,
        setup_quality=81.0,
        execution_quality=43.0,
        reward_quality=69.0,
        overall_trade_quality=64.0,
    )

    candidate = _candidate(
        layered_state=layered_state,
        score_dimensions=scores,
    )

    assert candidate.layered_state is layered_state
    assert candidate.score_dimensions is scores
    assert candidate.quality.entry_quality == 0.8


def test_candidate_default_contract_instances_are_not_shared() -> None:
    first = _candidate()
    second = _candidate()

    assert first.layered_state is not second.layered_state
    assert first.score_dimensions is not second.score_dimensions
