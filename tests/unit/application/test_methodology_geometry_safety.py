from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.application.methodology_geometry_safety import (
    GeometryRejectionCode,
    GeometrySafetyPolicy,
    GeometrySafetyState,
    LaneGeometryPolicy,
    evaluate_geometry_safety,
)
from apex.application.opportunity_portfolio import OpportunityLane
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


def _policy() -> GeometrySafetyPolicy:
    base = {
        OpportunityLane.CMP_SCALP: LaneGeometryPolicy(1.0, 2.0, 45.0),
        OpportunityLane.CONFIRMATION_SCALP: LaneGeometryPolicy(1.0, 2.0, 45.0),
        OpportunityLane.PULLBACK_SCALP: LaneGeometryPolicy(1.2, 2.5, 50.0),
        OpportunityLane.NEARBY_STRUCTURED: LaneGeometryPolicy(1.25, 6.0, 50.0),
        OpportunityLane.RUNNER: LaneGeometryPolicy(1.8, 8.0, 60.0),
        OpportunityLane.DEVELOPING: LaneGeometryPolicy(1.25, 6.0, 50.0),
    }
    return GeometrySafetyPolicy(lanes=base)


def _candidate(
    *,
    direction: TradeDirection = TradeDirection.LONG,
    target_prices: tuple[float, ...] = (103.0,),
) -> TradeCandidate:
    if direction is TradeDirection.LONG:
        entry = EntryZone(
            lower=99.5,
            upper=100.5,
            preferred=100.0,
            current_price=100.0,
            distance_from_current=0.0,
            atr_distance=0.0,
            estimated_move_missed=0.0,
            location_quality=0.9,
            mode=EntryMode.MARKET_NEAR,
            rationale=("test entry",),
        )
        invalidation = 98.5
    else:
        entry = EntryZone(
            lower=99.5,
            upper=100.5,
            preferred=100.0,
            current_price=100.0,
            distance_from_current=0.0,
            atr_distance=0.0,
            estimated_move_missed=0.0,
            location_quality=0.9,
            mode=EntryMode.MARKET_NEAR,
            rationale=("test entry",),
        )
        invalidation = 101.5

    return TradeCandidate(
        symbol="TESTUSDT",
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        direction=direction,
        decision_time=datetime(2026, 7, 21, tzinfo=UTC),
        entry=entry,
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=invalidation,
            rationale=("test invalidation",),
        ),
        targets=TargetConcept(
            levels=tuple(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=price,
                    label=f"TP{index}",
                    rationale=("test target",),
                )
                for index, price in enumerate(target_prices, start=1)
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


def test_valid_cost_adjusted_cmp_scalp_passes() -> None:
    result = evaluate_geometry_safety(
        _candidate(target_prices=(103.0,)),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=98.0,
        target_quality=70.0,
        expected_cost_pct=0.10,
        policy=_policy(),
    )

    assert result.state is GeometrySafetyState.PASS
    assert result.passed is True
    assert result.diagnostics.gross_tp1_reward_to_risk == pytest.approx(1.5)
    assert result.diagnostics.net_tp1_reward_to_risk == pytest.approx(2.9 / 2.1)


def test_low_reward_nearby_candidate_rejects_with_actual_and_required_values() -> None:
    result = evaluate_geometry_safety(
        _candidate(target_prices=(100.6,)),
        lane=OpportunityLane.NEARBY_STRUCTURED,
        executable_stop=98.0,
        target_quality=60.0,
        expected_cost_pct=0.0,
        policy=_policy(),
    )

    assert result.state is GeometrySafetyState.REJECT
    assert result.rejection_codes == (GeometryRejectionCode.TP1_BELOW_LANE_FLOOR,)
    assert result.diagnostics.net_tp1_reward_to_risk == pytest.approx(0.3)
    assert result.diagnostics.required_tp1_reward_to_risk == 1.25


def test_costs_eliminating_reward_reject() -> None:
    result = evaluate_geometry_safety(
        _candidate(target_prices=(100.6,)),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=98.0,
        target_quality=70.0,
        expected_cost_pct=0.70,
        policy=_policy(),
    )

    assert GeometryRejectionCode.COSTS_ELIMINATE_REWARD in result.rejection_codes


def test_unavailable_costs_are_incomplete_not_zero() -> None:
    result = evaluate_geometry_safety(
        _candidate(),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=98.0,
        target_quality=70.0,
        expected_cost_pct=None,
        policy=_policy(),
    )

    assert result.state is GeometrySafetyState.INCOMPLETE
    assert result.diagnostics.net_tp1_reward_to_risk is None
    assert result.rejection_codes == (GeometryRejectionCode.COSTS_UNAVAILABLE,)


def test_wrong_side_or_inside_stop_rejects() -> None:
    result = evaluate_geometry_safety(
        _candidate(),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=100.0,
        target_quality=70.0,
        expected_cost_pct=0.0,
        policy=_policy(),
    )

    assert GeometryRejectionCode.WRONG_SIDE_STOP in result.rejection_codes


def test_target_order_is_direction_aware() -> None:
    long_result = evaluate_geometry_safety(
        _candidate(target_prices=(104.0, 103.0)),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=98.0,
        target_quality=70.0,
        expected_cost_pct=0.0,
        policy=_policy(),
    )
    short_result = evaluate_geometry_safety(
        _candidate(
            direction=TradeDirection.SHORT,
            target_prices=(96.0, 97.0),
        ),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=102.0,
        target_quality=70.0,
        expected_cost_pct=0.0,
        policy=_policy(),
    )

    assert GeometryRejectionCode.TARGET_ORDER_INVALID in long_result.rejection_codes
    assert GeometryRejectionCode.TARGET_ORDER_INVALID in short_result.rejection_codes


def test_stop_distance_and_target_quality_are_hard_floors() -> None:
    result = evaluate_geometry_safety(
        _candidate(target_prices=(110.0,)),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=95.0,
        target_quality=20.0,
        expected_cost_pct=0.0,
        policy=_policy(),
    )

    assert GeometryRejectionCode.STOP_DISTANCE_EXCEEDS_LANE_LIMIT in result.rejection_codes
    assert GeometryRejectionCode.TARGET_QUALITY_BELOW_FLOOR in result.rejection_codes


def test_policy_requires_every_lane() -> None:
    with pytest.raises(ValueError, match="missing lanes"):
        GeometrySafetyPolicy(
            lanes={
                OpportunityLane.CMP_SCALP: LaneGeometryPolicy(1.0, 2.0, 45.0),
            }
        )
