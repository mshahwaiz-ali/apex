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
    target_type: TargetType = TargetType.STRUCTURAL,
    target_types: tuple[TargetType, ...] | None = None,
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
                    kind=(target_type if target_types is None else target_types[index - 1]),
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
    assert result.diagnostics.gross_reward_distance == pytest.approx(3.0)
    assert result.diagnostics.net_reward_distance == pytest.approx(2.9)
    assert result.diagnostics.gross_risk_distance == pytest.approx(2.0)
    assert result.diagnostics.net_risk_distance == pytest.approx(2.1)
    assert result.diagnostics.cost_distance == pytest.approx(0.1)
    assert result.diagnostics.stop_to_cost_ratio == pytest.approx(20.0)
    assert result.diagnostics.target_to_cost_ratio == pytest.approx(30.0)
    assert result.diagnostics.cost_drag_on_reward_pct == pytest.approx(100.0 / 30.0)
    assert result.diagnostics.cost_drag_on_gross_rr_pct == pytest.approx(
        (1.5 - (2.9 / 2.1)) / 1.5 * 100.0
    )


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
    assert result.diagnostics.cost_distance is None
    assert result.diagnostics.stop_to_cost_ratio is None
    assert result.diagnostics.target_to_cost_ratio is None
    assert result.diagnostics.cost_drag_on_reward_pct is None
    assert result.diagnostics.cost_drag_on_gross_rr_pct is None
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


def test_stop_must_clear_atr_noise_floor() -> None:
    policy = _policy()
    result = evaluate_geometry_safety(
        _candidate(),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=99.4,
        target_quality=70.0,
        expected_cost_pct=0.10,
        decision_atr=4.0,
        policy=policy,
    )

    assert GeometryRejectionCode.STOP_DISTANCE_BELOW_NOISE_FLOOR in result.rejection_codes
    assert result.diagnostics.stop_distance_atr == pytest.approx(0.15)


def test_stop_must_clear_round_trip_cost_floor() -> None:
    result = evaluate_geometry_safety(
        _candidate(),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=99.4,
        target_quality=70.0,
        expected_cost_pct=0.50,
        policy=_policy(),
    )

    assert GeometryRejectionCode.STOP_DISTANCE_BELOW_COST_FLOOR in result.rejection_codes
    assert result.diagnostics.cost_distance == pytest.approx(0.5)
    assert result.diagnostics.stop_to_cost_ratio == pytest.approx(1.2)
    assert result.diagnostics.target_to_cost_ratio == pytest.approx(6.0)


def test_zero_costs_keep_explicit_zero_drag_without_division_ratios() -> None:
    result = evaluate_geometry_safety(
        _candidate(target_prices=(103.0,)),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=98.0,
        target_quality=70.0,
        expected_cost_pct=0.0,
        policy=_policy(),
    )

    assert result.diagnostics.cost_distance == pytest.approx(0.0)
    assert result.diagnostics.net_reward_distance == pytest.approx(3.0)
    assert result.diagnostics.net_risk_distance == pytest.approx(2.0)
    assert result.diagnostics.stop_to_cost_ratio is None
    assert result.diagnostics.target_to_cost_ratio is None
    assert result.diagnostics.cost_drag_on_reward_pct == pytest.approx(0.0)
    assert result.diagnostics.cost_drag_on_gross_rr_pct == pytest.approx(0.0)


def test_scalp_tp1_must_fit_lane_atr_horizon() -> None:
    policy = GeometrySafetyPolicy(
        lanes={
            **_policy().lanes,
            OpportunityLane.CMP_SCALP: LaneGeometryPolicy(
                1.0,
                2.0,
                45.0,
                maximum_tp1_distance_atr=1.5,
            ),
        }
    )
    result = evaluate_geometry_safety(
        _candidate(target_prices=(104.0,)),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=98.0,
        target_quality=70.0,
        expected_cost_pct=0.10,
        decision_atr=2.0,
        policy=policy,
    )

    assert GeometryRejectionCode.TP1_EXCEEDS_LANE_HORIZON in result.rejection_codes
    assert result.diagnostics.tp1_distance_atr == pytest.approx(2.0)


def test_scalp_tp1_cannot_be_expansion_projection_only() -> None:
    result = evaluate_geometry_safety(
        _candidate(target_type=TargetType.EXPANSION),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=98.0,
        target_quality=70.0,
        expected_cost_pct=0.10,
        policy=_policy(),
    )

    assert GeometryRejectionCode.SCALP_TP1_REQUIRES_VERIFIED_STRUCTURE in result.rejection_codes


def test_policy_requires_every_lane() -> None:
    with pytest.raises(ValueError, match="missing lanes"):
        GeometrySafetyPolicy(
            lanes={
                OpportunityLane.CMP_SCALP: LaneGeometryPolicy(1.0, 2.0, 45.0),
            }
        )


def test_cost_adjusted_minimum_viable_tp1_long_and_short() -> None:
    long_result = evaluate_geometry_safety(
        _candidate(target_prices=(103.0,)),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=98.0,
        target_quality=70.0,
        expected_cost_pct=0.10,
        decision_atr=2.0,
        policy=_policy(),
    )
    short_result = evaluate_geometry_safety(
        _candidate(direction=TradeDirection.SHORT, target_prices=(97.0,)),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=102.0,
        target_quality=70.0,
        expected_cost_pct=0.10,
        decision_atr=2.0,
        policy=_policy(),
    )

    assert long_result.diagnostics.minimum_viable_tp1_distance == pytest.approx(2.2)
    assert long_result.diagnostics.minimum_viable_tp1_price == pytest.approx(102.2)
    assert long_result.diagnostics.minimum_viable_tp1_distance_atr == pytest.approx(1.1)
    assert short_result.diagnostics.minimum_viable_tp1_price == pytest.approx(97.8)


def test_farther_existing_target_can_rescue_infeasible_current_tp1() -> None:
    result = evaluate_geometry_safety(
        _candidate(target_prices=(101.0, 103.0)),
        lane=OpportunityLane.NEARBY_STRUCTURED,
        executable_stop=98.0,
        target_quality=70.0,
        expected_cost_pct=0.10,
        decision_atr=2.0,
        policy=_policy(),
    )

    assert result.diagnostics.tp1_feasibility_gap > 0.0
    assert result.diagnostics.geometry_feasible_before_quality is True
    assert result.diagnostics.feasible_existing_target_count == 1
    assert result.diagnostics.nearest_feasible_existing_target_price == pytest.approx(103.0)
    assert result.diagnostics.nearest_feasible_existing_target_index == 2
    assert result.diagnostics.no_feasible_target_reason is None


def test_no_existing_target_feasible_is_explicit() -> None:
    result = evaluate_geometry_safety(
        _candidate(target_prices=(100.6, 101.0)),
        lane=OpportunityLane.NEARBY_STRUCTURED,
        executable_stop=98.0,
        target_quality=70.0,
        expected_cost_pct=0.10,
        policy=_policy(),
    )

    assert result.diagnostics.geometry_feasible_before_quality is False
    assert result.diagnostics.feasible_existing_target_count == 0
    assert result.diagnostics.no_feasible_target_reason.value == "no_existing_target_feasible"


def test_minimum_viable_tp1_beyond_lane_horizon_is_explicit() -> None:
    policy = GeometrySafetyPolicy(
        lanes={
            **_policy().lanes,
            OpportunityLane.CMP_SCALP: LaneGeometryPolicy(
                1.0, 2.0, 45.0, maximum_tp1_distance_atr=1.0
            ),
        }
    )
    result = evaluate_geometry_safety(
        _candidate(target_prices=(103.0,)),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=98.0,
        target_quality=70.0,
        expected_cost_pct=0.10,
        decision_atr=2.0,
        policy=policy,
    )

    assert result.diagnostics.minimum_viable_tp1_distance_atr == pytest.approx(1.1)
    assert (
        result.diagnostics.no_feasible_target_reason.value
        == "minimum_viable_tp1_beyond_lane_horizon"
    )


def test_cost_only_target_infeasibility_is_distinguished() -> None:
    result = evaluate_geometry_safety(
        _candidate(target_prices=(102.0,)),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=98.0,
        target_quality=70.0,
        expected_cost_pct=0.10,
        policy=_policy(),
    )

    assert result.diagnostics.gross_tp1_reward_to_risk == pytest.approx(1.0)
    assert result.diagnostics.net_tp1_reward_to_risk < 1.0
    assert result.diagnostics.no_feasible_target_reason.value == "cost_only_infeasibility"


def test_scalp_expansion_target_can_be_skipped_for_verified_farther_target() -> None:
    result = evaluate_geometry_safety(
        _candidate(
            target_prices=(103.0, 104.0),
            target_types=(TargetType.EXPANSION, TargetType.STRUCTURAL),
        ),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=98.0,
        target_quality=70.0,
        expected_cost_pct=0.10,
        decision_atr=2.0,
        policy=_policy(),
    )

    assert result.diagnostics.geometry_feasible_before_quality is True
    assert result.diagnostics.nearest_feasible_existing_target_index == 2


def test_scalp_expansion_only_target_reports_target_type_infeasibility() -> None:
    result = evaluate_geometry_safety(
        _candidate(target_prices=(103.0,), target_type=TargetType.EXPANSION),
        lane=OpportunityLane.CMP_SCALP,
        executable_stop=98.0,
        target_quality=70.0,
        expected_cost_pct=0.10,
        policy=_policy(),
    )

    assert result.diagnostics.geometry_feasible_before_quality is False
    assert result.diagnostics.no_feasible_target_reason.value == "target_type_only_infeasibility"
