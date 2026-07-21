from __future__ import annotations

from datetime import UTC, datetime

from apex.application.methodology_candidate_lane_horizon import (
    measure_candidate_lane_horizon,
)
from apex.application.methodology_horizon_contracts import HoldingHorizon
from apex.application.methodology_lane_horizon import LifecycleModel
from apex.application.opportunity_portfolio import OpportunityLane
from apex.domain.methodology_contracts import LayeredStateSnapshot, ScoreDimensions
from apex.strategies.contracts import (
    CandidateLifecycle,
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
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


def _candidate(
    *,
    current_price: float = 100.0,
    lower: float = 99.5,
    upper: float = 100.5,
    preferred: float = 100.0,
    max_chase_price: float | None = 101.0,
    atr_distance: float = 0.0,
    metadata: dict[str, str | int | float | bool] | None = None,
    direction: TradeDirection = TradeDirection.LONG,
) -> TradeCandidate:
    if direction is TradeDirection.LONG:
        invalidation_price = 98.0
        target_price = 104.0
    else:
        invalidation_price = 102.0
        target_price = 96.0

    return TradeCandidate(
        symbol="TESTUSDT",
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        direction=direction,
        decision_time=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
        entry=EntryZone(
            lower=lower,
            upper=upper,
            preferred=preferred,
            current_price=current_price,
            distance_from_current=abs(current_price - preferred),
            atr_distance=atr_distance,
            estimated_move_missed=0.0,
            location_quality=0.9,
            mode=EntryMode.MARKET_NEAR,
            rationale=("test entry geometry",),
            max_chase_price=max_chase_price,
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=invalidation_price,
            rationale=("test invalidation",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=target_price,
                    label="TP1",
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
        metadata=metadata
        or {
            "execution_timeframe": "5m",
            "setup_timeframe": "30m",
            "invalidation_timeframe": "5m",
            "target_timeframe": "30m",
            "expected_bars_to_target": 16,
            "decision_atr": 2.0,
            "lifecycle_model": LifecycleModel.STRUCTURED.value,
        },
        lifecycle=CandidateLifecycle(),
        layered_state=LayeredStateSnapshot(),
        score_dimensions=ScoreDimensions(),
    )


def test_cmp_inside_zone_becomes_current_confirmation() -> None:
    result = measure_candidate_lane_horizon(
        _candidate(),
        entry_status=EntryStatus.WATCH_NEAR_ENTRY,
    )

    assert result.available is True
    assert result.assessment is not None
    assert result.assessment.lane is OpportunityLane.CONFIRMATION_SCALP
    assert result.assessment.current_at_cmp is True
    assert result.assessment.holding_horizon is HoldingHorizon.STRUCTURED


def test_entry_away_from_cmp_remains_nearby() -> None:
    result = measure_candidate_lane_horizon(
        _candidate(
            current_price=95.0,
            atr_distance=2.5,
            max_chase_price=101.0,
        ),
        entry_status=EntryStatus.WATCH_NEAR_ENTRY,
    )

    assert result.assessment is not None
    assert result.assessment.lane is OpportunityLane.NEARBY_STRUCTURED
    assert result.assessment.current_at_cmp is False


def test_direction_aware_max_chase_breach_becomes_developing() -> None:
    long_result = measure_candidate_lane_horizon(
        _candidate(current_price=102.0),
        entry_status=EntryStatus.LATE_OR_CHASING,
    )
    short_result = measure_candidate_lane_horizon(
        _candidate(
            direction=TradeDirection.SHORT,
            current_price=94.0,
            lower=99.5,
            upper=100.5,
            preferred=100.0,
            max_chase_price=95.0,
            atr_distance=3.0,
        ),
        entry_status=EntryStatus.LATE_OR_CHASING,
    )

    assert long_result.assessment is not None
    assert short_result.assessment is not None
    assert long_result.assessment.lane is OpportunityLane.DEVELOPING
    assert short_result.assessment.lane is OpportunityLane.DEVELOPING


def test_missing_measurement_preserves_explicit_fallback() -> None:
    result = measure_candidate_lane_horizon(
        _candidate(
            metadata={
                "execution_timeframe": "5m",
                "setup_timeframe": "5m",
                "decision_atr": 2.0,
                "lifecycle_model": LifecycleModel.SCALP.value,
            }
        ),
        entry_status=EntryStatus.READY_NOW,
    )

    assert result.available is False
    assert result.assessment is None
    assert result.missing_measurements == ("expected_bars_to_target",)


def test_expiry_bars_are_not_fabricated_as_expected_target_bars() -> None:
    result = measure_candidate_lane_horizon(
        _candidate(
            metadata={
                "execution_timeframe": "5m",
                "setup_timeframe": "5m",
                "invalidation_timeframe": "5m",
                "target_timeframe": "5m",
                "decision_atr": 2.0,
                "lifecycle_model": LifecycleModel.SCALP.value,
            }
        ),
        entry_status=EntryStatus.READY_NOW,
    )

    assert result.available is False
    assert result.assessment is None
    assert "expected_bars_to_target" in result.missing_measurements


def test_runner_requires_explicit_authority() -> None:
    candidate = _candidate(
        metadata={
            "execution_timeframe": "5m",
            "setup_timeframe": "30m",
            "invalidation_timeframe": "30m",
            "target_timeframe": "60m",
            "expected_bars_to_target": 30,
            "decision_atr": 2.0,
            "lifecycle_model": LifecycleModel.RUNNER.value,
        }
    )

    unavailable = measure_candidate_lane_horizon(
        candidate,
        entry_status=EntryStatus.READY_NOW,
    )
    denied = measure_candidate_lane_horizon(
        candidate,
        entry_status=EntryStatus.READY_NOW,
        runner_authority=False,
    )
    allowed = measure_candidate_lane_horizon(
        candidate,
        entry_status=EntryStatus.READY_NOW,
        runner_authority=True,
    )

    assert unavailable.available is False
    assert "runner_authority" in unavailable.missing_measurements
    assert denied.assessment is not None
    assert denied.assessment.lane is OpportunityLane.DEVELOPING
    assert allowed.assessment is not None
    assert allowed.assessment.lane is OpportunityLane.RUNNER
