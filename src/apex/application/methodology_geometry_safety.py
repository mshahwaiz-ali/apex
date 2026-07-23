"""Lane-aware hard geometry safety assessment.

This module centralizes the mathematics required by the Batch 6 geometry gate.
It does not mutate candidates or portfolio selection. Callers must provide an
explicit policy and explicit expected execution costs; unavailable costs remain
an incomplete assessment rather than being treated as zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.application.opportunity_portfolio import OpportunityLane
from apex.strategies.contracts import TargetType, TradeCandidate, TradeDirection


class GeometrySafetyState(StrEnum):
    PASS = "pass"
    REJECT = "reject"
    INCOMPLETE = "incomplete"


class NoFeasibleTargetReason(StrEnum):
    NO_EXISTING_TARGET_FEASIBLE = "no_existing_target_feasible"
    MINIMUM_VIABLE_TP1_BEYOND_LANE_HORIZON = "minimum_viable_tp1_beyond_lane_horizon"
    COST_ONLY_INFEASIBILITY = "cost_only_infeasibility"
    TARGET_TYPE_ONLY_INFEASIBILITY = "target_type_only_infeasibility"


class GeometryRejectionCode(StrEnum):
    COSTS_UNAVAILABLE = "costs_unavailable"
    WRONG_SIDE_STOP = "wrong_side_stop"
    STOP_INSIDE_ENTRY_ZONE = "stop_inside_entry_zone"
    WRONG_SIDE_TARGET = "wrong_side_target"
    TARGET_ORDER_INVALID = "target_order_invalid"
    TP1_BELOW_LANE_FLOOR = "tp1_below_lane_floor"
    STOP_DISTANCE_EXCEEDS_LANE_LIMIT = "stop_distance_exceeds_lane_limit"
    STOP_DISTANCE_BELOW_NOISE_FLOOR = "stop_distance_below_noise_floor"
    STOP_DISTANCE_BELOW_COST_FLOOR = "stop_distance_below_cost_floor"
    TP1_EXCEEDS_LANE_HORIZON = "tp1_exceeds_lane_horizon"
    SCALP_TP1_REQUIRES_VERIFIED_STRUCTURE = "scalp_tp1_requires_verified_structure"
    TARGET_QUALITY_BELOW_FLOOR = "target_quality_below_floor"
    COSTS_ELIMINATE_REWARD = "costs_eliminate_reward"


@dataclass(frozen=True, slots=True)
class LaneGeometryPolicy:
    minimum_tp1_reward_to_risk: float
    maximum_stop_distance_pct: float
    minimum_target_quality: float
    minimum_stop_distance_atr: float = 0.25
    minimum_stop_to_cost_ratio: float = 1.25
    maximum_tp1_distance_atr: float | None = None

    def __post_init__(self) -> None:
        values = (
            self.minimum_tp1_reward_to_risk,
            self.maximum_stop_distance_pct,
            self.minimum_target_quality,
            self.minimum_stop_distance_atr,
            self.minimum_stop_to_cost_ratio,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("lane geometry policy values must be finite")
        if self.minimum_tp1_reward_to_risk <= 0.0:
            raise ValueError("minimum TP1 reward-to-risk must be positive")
        if self.maximum_stop_distance_pct <= 0.0:
            raise ValueError("maximum stop distance percentage must be positive")
        if not 0.0 <= self.minimum_target_quality <= 100.0:
            raise ValueError("minimum target quality must be between zero and 100")
        if self.minimum_stop_distance_atr < 0.0:
            raise ValueError("minimum stop ATR distance cannot be negative")
        if self.minimum_stop_to_cost_ratio < 0.0:
            raise ValueError("minimum stop-to-cost ratio cannot be negative")
        if self.maximum_tp1_distance_atr is not None:
            if not math.isfinite(self.maximum_tp1_distance_atr):
                raise ValueError("maximum TP1 ATR distance must be finite")
            if self.maximum_tp1_distance_atr <= 0.0:
                raise ValueError("maximum TP1 ATR distance must be positive")


@dataclass(frozen=True, slots=True)
class GeometrySafetyPolicy:
    lanes: dict[OpportunityLane, LaneGeometryPolicy]

    def __post_init__(self) -> None:
        copied = dict(self.lanes)
        missing = tuple(lane for lane in OpportunityLane if lane not in copied)
        if missing:
            names = ", ".join(lane.value for lane in missing)
            raise ValueError(f"geometry policy is missing lanes: {names}")
        object.__setattr__(self, "lanes", copied)

    def for_lane(self, lane: OpportunityLane) -> LaneGeometryPolicy:
        return self.lanes[lane]


@dataclass(frozen=True, slots=True)
class GeometrySafetyDiagnostics:
    lane: OpportunityLane
    selected_entry: float
    entry_zone_low: float
    entry_zone_high: float
    executable_stop: float
    stop_distance_pct: float
    tp1_price: float
    gross_tp1_reward_to_risk: float
    net_tp1_reward_to_risk: float | None
    gross_reward_distance: float
    net_reward_distance: float | None
    gross_risk_distance: float
    net_risk_distance: float | None
    cost_distance: float | None
    stop_to_cost_ratio: float | None
    target_to_cost_ratio: float | None
    cost_drag_on_reward_pct: float | None
    cost_drag_on_gross_rr_pct: float | None
    target_distance_pct: float
    expected_cost_pct: float | None
    target_quality: float
    required_tp1_reward_to_risk: float
    maximum_stop_distance_pct: float
    minimum_target_quality: float
    stop_distance_atr: float | None
    minimum_stop_distance_atr: float
    minimum_stop_to_cost_ratio: float
    tp1_distance_atr: float | None
    maximum_tp1_distance_atr: float | None
    minimum_viable_tp1_price: float | None
    minimum_viable_tp1_distance: float | None
    minimum_viable_tp1_distance_atr: float | None
    available_tp1_price: float
    available_tp1_distance: float
    available_tp1_distance_atr: float | None
    tp1_feasibility_gap: float | None
    tp1_feasibility_gap_atr: float | None
    geometry_feasible_before_quality: bool | None
    feasible_existing_target_count: int | None
    nearest_feasible_existing_target_price: float | None
    nearest_feasible_existing_target_index: int | None
    no_feasible_target_reason: NoFeasibleTargetReason | None


@dataclass(frozen=True, slots=True)
class GeometrySafetyAssessment:
    state: GeometrySafetyState
    diagnostics: GeometrySafetyDiagnostics
    rejection_codes: tuple[GeometryRejectionCode, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.reasons:
            raise ValueError("geometry safety assessment requires reasons")
        if len(set(self.rejection_codes)) != len(self.rejection_codes):
            raise ValueError("geometry rejection codes must be unique")
        if self.state is GeometrySafetyState.PASS and self.rejection_codes:
            raise ValueError("passing geometry cannot contain rejection codes")
        if self.state is not GeometrySafetyState.PASS and not self.rejection_codes:
            raise ValueError("non-passing geometry requires rejection codes")

    @property
    def passed(self) -> bool:
        return self.state is GeometrySafetyState.PASS


def evaluate_geometry_safety(
    candidate: TradeCandidate,
    *,
    lane: OpportunityLane,
    executable_stop: float,
    target_quality: float,
    expected_cost_pct: float | None,
    decision_atr: float | None = None,
    policy: GeometrySafetyPolicy,
    selected_entry: float | None = None,
) -> GeometrySafetyAssessment:
    """Evaluate one candidate against explicit lane-aware geometry policy."""

    _positive_finite("executable stop", executable_stop)
    _bounded_score("target quality", target_quality)
    if expected_cost_pct is not None:
        _non_negative_finite("expected cost percentage", expected_cost_pct)
    if decision_atr is not None:
        _positive_finite("decision ATR", decision_atr)

    lane_policy = policy.for_lane(lane)
    selected_entry = candidate.entry.preferred if selected_entry is None else selected_entry
    _positive_finite("selected entry", selected_entry)
    tp1 = candidate.targets.levels[0]
    stop_distance = abs(selected_entry - executable_stop)
    stop_distance_pct = stop_distance / selected_entry * 100.0
    target_distance = abs(tp1.price - selected_entry)
    target_distance_pct = target_distance / selected_entry * 100.0
    gross_rr = target_distance / stop_distance if stop_distance > 0.0 else 0.0
    stop_distance_atr = None if decision_atr is None else stop_distance / decision_atr
    tp1_distance_atr = None if decision_atr is None else target_distance / decision_atr

    cost_distance: float | None = None
    net_reward: float | None = None
    net_risk: float | None = None
    net_rr: float | None = None
    stop_to_cost_ratio: float | None = None
    target_to_cost_ratio: float | None = None
    cost_drag_on_reward_pct: float | None = None
    cost_drag_on_gross_rr_pct: float | None = None
    if expected_cost_pct is not None:
        cost_distance = selected_entry * expected_cost_pct / 100.0
        net_reward = target_distance - cost_distance
        net_risk = stop_distance + cost_distance
        net_rr = net_reward / net_risk if net_risk > 0.0 else 0.0
        if cost_distance > 0.0:
            stop_to_cost_ratio = stop_distance / cost_distance
            target_to_cost_ratio = target_distance / cost_distance
        if target_distance > 0.0:
            cost_drag_on_reward_pct = cost_distance / target_distance * 100.0
        if gross_rr > 0.0 and net_rr is not None:
            cost_drag_on_gross_rr_pct = (gross_rr - net_rr) / gross_rr * 100.0

    feasibility = _existing_target_feasibility(
        candidate,
        lane=lane,
        selected_entry=selected_entry,
        stop_distance=stop_distance,
        cost_distance=cost_distance,
        decision_atr=decision_atr,
        policy=lane_policy,
    )

    diagnostics = GeometrySafetyDiagnostics(
        lane=lane,
        selected_entry=selected_entry,
        entry_zone_low=candidate.entry.lower,
        entry_zone_high=candidate.entry.upper,
        executable_stop=executable_stop,
        stop_distance_pct=stop_distance_pct,
        tp1_price=tp1.price,
        gross_tp1_reward_to_risk=gross_rr,
        net_tp1_reward_to_risk=net_rr,
        gross_reward_distance=target_distance,
        net_reward_distance=net_reward,
        gross_risk_distance=stop_distance,
        net_risk_distance=net_risk,
        cost_distance=cost_distance,
        stop_to_cost_ratio=stop_to_cost_ratio,
        target_to_cost_ratio=target_to_cost_ratio,
        cost_drag_on_reward_pct=cost_drag_on_reward_pct,
        cost_drag_on_gross_rr_pct=cost_drag_on_gross_rr_pct,
        target_distance_pct=target_distance_pct,
        expected_cost_pct=expected_cost_pct,
        target_quality=target_quality,
        required_tp1_reward_to_risk=lane_policy.minimum_tp1_reward_to_risk,
        maximum_stop_distance_pct=lane_policy.maximum_stop_distance_pct,
        minimum_target_quality=lane_policy.minimum_target_quality,
        stop_distance_atr=stop_distance_atr,
        minimum_stop_distance_atr=lane_policy.minimum_stop_distance_atr,
        minimum_stop_to_cost_ratio=lane_policy.minimum_stop_to_cost_ratio,
        tp1_distance_atr=tp1_distance_atr,
        maximum_tp1_distance_atr=lane_policy.maximum_tp1_distance_atr,
        minimum_viable_tp1_price=feasibility.minimum_viable_tp1_price,
        minimum_viable_tp1_distance=feasibility.minimum_viable_tp1_distance,
        minimum_viable_tp1_distance_atr=feasibility.minimum_viable_tp1_distance_atr,
        available_tp1_price=tp1.price,
        available_tp1_distance=target_distance,
        available_tp1_distance_atr=tp1_distance_atr,
        tp1_feasibility_gap=feasibility.tp1_feasibility_gap,
        tp1_feasibility_gap_atr=feasibility.tp1_feasibility_gap_atr,
        geometry_feasible_before_quality=feasibility.geometry_feasible_before_quality,
        feasible_existing_target_count=feasibility.feasible_existing_target_count,
        nearest_feasible_existing_target_price=(feasibility.nearest_feasible_existing_target_price),
        nearest_feasible_existing_target_index=(feasibility.nearest_feasible_existing_target_index),
        no_feasible_target_reason=feasibility.no_feasible_target_reason,
    )

    if expected_cost_pct is None:
        return GeometrySafetyAssessment(
            state=GeometrySafetyState.INCOMPLETE,
            diagnostics=diagnostics,
            rejection_codes=(GeometryRejectionCode.COSTS_UNAVAILABLE,),
            reasons=(
                "expected fees and slippage are unavailable; geometry safety cannot "
                "claim a cost-adjusted pass",
            ),
        )

    codes: list[GeometryRejectionCode] = []
    reasons: list[str] = []

    stop_wrong_side = (
        executable_stop >= candidate.entry.lower
        if candidate.direction is TradeDirection.LONG
        else executable_stop <= candidate.entry.upper
    )
    if stop_wrong_side:
        codes.append(GeometryRejectionCode.WRONG_SIDE_STOP)
        reasons.append("executable stop is not outside the entry zone on the risk side")
    elif candidate.entry.lower <= executable_stop <= candidate.entry.upper:
        codes.append(GeometryRejectionCode.STOP_INSIDE_ENTRY_ZONE)
        reasons.append("executable stop lies inside the entry zone")

    target_prices = tuple(level.price for level in candidate.targets.levels)
    if candidate.direction is TradeDirection.LONG:
        wrong_side_target = any(price <= selected_entry for price in target_prices)
        invalid_order = target_prices != tuple(sorted(target_prices))
    else:
        wrong_side_target = any(price >= selected_entry for price in target_prices)
        invalid_order = target_prices != tuple(sorted(target_prices, reverse=True))

    if wrong_side_target:
        codes.append(GeometryRejectionCode.WRONG_SIDE_TARGET)
        reasons.append("one or more targets are on the wrong side of selected entry")
    if invalid_order:
        codes.append(GeometryRejectionCode.TARGET_ORDER_INVALID)
        reasons.append("targets are not ordered away from selected entry")

    if net_rr is not None and net_rr <= 0.0:
        codes.append(GeometryRejectionCode.COSTS_ELIMINATE_REWARD)
        reasons.append("expected fees and slippage eliminate TP1 reward")
    elif net_rr is not None and net_rr < lane_policy.minimum_tp1_reward_to_risk:
        codes.append(GeometryRejectionCode.TP1_BELOW_LANE_FLOOR)
        reasons.append(
            f"net TP1 reward-to-risk {net_rr:.4f} is below "
            f"{lane_policy.minimum_tp1_reward_to_risk:.4f} required for {lane.value}"
        )

    if stop_distance_pct > lane_policy.maximum_stop_distance_pct:
        codes.append(GeometryRejectionCode.STOP_DISTANCE_EXCEEDS_LANE_LIMIT)
        reasons.append(
            f"stop distance {stop_distance_pct:.4f}% exceeds "
            f"{lane_policy.maximum_stop_distance_pct:.4f}% allowed for {lane.value}"
        )

    if (
        stop_distance_atr is not None
        and stop_distance_atr + 1e-9 < lane_policy.minimum_stop_distance_atr
    ):
        codes.append(GeometryRejectionCode.STOP_DISTANCE_BELOW_NOISE_FLOOR)
        reasons.append(
            f"stop distance {stop_distance_atr:.4f} ATR is below the "
            f"{lane_policy.minimum_stop_distance_atr:.4f} ATR noise floor for {lane.value}"
        )

    if (
        stop_to_cost_ratio is not None
        and stop_to_cost_ratio + 1e-9 < lane_policy.minimum_stop_to_cost_ratio
    ):
        codes.append(GeometryRejectionCode.STOP_DISTANCE_BELOW_COST_FLOOR)
        reasons.append(
            f"stop distance is {stop_to_cost_ratio:.4f}x expected round-trip costs, below "
            f"the {lane_policy.minimum_stop_to_cost_ratio:.4f}x floor for {lane.value}"
        )

    maximum_target_atr = lane_policy.maximum_tp1_distance_atr
    if (
        maximum_target_atr is not None
        and tp1_distance_atr is not None
        and tp1_distance_atr > maximum_target_atr + 1e-9
    ):
        codes.append(GeometryRejectionCode.TP1_EXCEEDS_LANE_HORIZON)
        reasons.append(
            f"TP1 distance {tp1_distance_atr:.4f} ATR exceeds the "
            f"{maximum_target_atr:.4f} ATR horizon for {lane.value}"
        )

    if lane.is_scalp and getattr(tp1, "kind", None) is TargetType.EXPANSION:
        codes.append(GeometryRejectionCode.SCALP_TP1_REQUIRES_VERIFIED_STRUCTURE)
        reasons.append(
            "scalp TP1 must use nearby structural, liquidity, range, or partial evidence; "
            "an expansion projection alone is not executable"
        )

    if target_quality < lane_policy.minimum_target_quality:
        codes.append(GeometryRejectionCode.TARGET_QUALITY_BELOW_FLOOR)
        reasons.append(
            f"target quality {target_quality:.4f} is below "
            f"{lane_policy.minimum_target_quality:.4f} required for {lane.value}"
        )

    if codes:
        return GeometrySafetyAssessment(
            state=GeometrySafetyState.REJECT,
            diagnostics=diagnostics,
            rejection_codes=tuple(codes),
            reasons=tuple(reasons),
        )

    return GeometrySafetyAssessment(
        state=GeometrySafetyState.PASS,
        diagnostics=diagnostics,
        rejection_codes=(),
        reasons=(
            "entry, executable stop, ordered targets, cost-adjusted TP1 reward, "
            "stop distance, and target quality satisfy the lane policy",
        ),
    )


@dataclass(frozen=True, slots=True)
class _ExistingTargetFeasibility:
    minimum_viable_tp1_price: float | None
    minimum_viable_tp1_distance: float | None
    minimum_viable_tp1_distance_atr: float | None
    tp1_feasibility_gap: float | None
    tp1_feasibility_gap_atr: float | None
    geometry_feasible_before_quality: bool | None
    feasible_existing_target_count: int | None
    nearest_feasible_existing_target_price: float | None
    nearest_feasible_existing_target_index: int | None
    no_feasible_target_reason: NoFeasibleTargetReason | None


def _existing_target_feasibility(
    candidate: TradeCandidate,
    *,
    lane: OpportunityLane,
    selected_entry: float,
    stop_distance: float,
    cost_distance: float | None,
    decision_atr: float | None,
    policy: LaneGeometryPolicy,
) -> _ExistingTargetFeasibility:
    if cost_distance is None:
        return _ExistingTargetFeasibility(
            minimum_viable_tp1_price=None,
            minimum_viable_tp1_distance=None,
            minimum_viable_tp1_distance_atr=None,
            tp1_feasibility_gap=None,
            tp1_feasibility_gap_atr=None,
            geometry_feasible_before_quality=None,
            feasible_existing_target_count=None,
            nearest_feasible_existing_target_price=None,
            nearest_feasible_existing_target_index=None,
            no_feasible_target_reason=None,
        )

    net_risk = stop_distance + cost_distance
    minimum_distance = policy.minimum_tp1_reward_to_risk * net_risk + cost_distance
    minimum_price = (
        selected_entry + minimum_distance
        if candidate.direction is TradeDirection.LONG
        else selected_entry - minimum_distance
    )
    minimum_distance_atr = None if decision_atr is None else minimum_distance / decision_atr
    available_distance = abs(candidate.targets.levels[0].price - selected_entry)
    gap = max(0.0, minimum_distance - available_distance)
    gap_atr = None if decision_atr is None else gap / decision_atr

    feasible: list[tuple[int, float, float]] = []
    cost_only = False
    target_type_only = False
    maximum_target_atr = policy.maximum_tp1_distance_atr

    for index, level in enumerate(candidate.targets.levels, start=1):
        price = level.price
        correct_side = (
            price > selected_entry
            if candidate.direction is TradeDirection.LONG
            else price < selected_entry
        )
        if not correct_side:
            continue
        distance = abs(price - selected_entry)
        gross_rr = distance / stop_distance if stop_distance > 0.0 else 0.0
        net_reward = distance - cost_distance
        net_rr = net_reward / net_risk if net_risk > 0.0 else 0.0
        distance_atr = None if decision_atr is None else distance / decision_atr
        horizon_ok = (
            maximum_target_atr is None
            or distance_atr is None
            or distance_atr <= maximum_target_atr + 1e-9
        )
        type_ok = not (lane.is_scalp and level.kind is TargetType.EXPANSION)
        reward_ok = net_rr + 1e-9 >= policy.minimum_tp1_reward_to_risk

        if reward_ok and horizon_ok and not type_ok:
            target_type_only = True
        if (
            cost_distance > 0.0
            and gross_rr + 1e-9 >= policy.minimum_tp1_reward_to_risk
            and not reward_ok
            and horizon_ok
            and type_ok
        ):
            cost_only = True
        if reward_ok and horizon_ok and type_ok:
            feasible.append((index, price, distance))

    feasible.sort(key=lambda item: (item[2], item[0]))
    no_reason: NoFeasibleTargetReason | None = None
    if not feasible:
        if (
            maximum_target_atr is not None
            and minimum_distance_atr is not None
            and minimum_distance_atr > maximum_target_atr + 1e-9
        ):
            no_reason = NoFeasibleTargetReason.MINIMUM_VIABLE_TP1_BEYOND_LANE_HORIZON
        elif target_type_only:
            no_reason = NoFeasibleTargetReason.TARGET_TYPE_ONLY_INFEASIBILITY
        elif cost_only:
            no_reason = NoFeasibleTargetReason.COST_ONLY_INFEASIBILITY
        else:
            no_reason = NoFeasibleTargetReason.NO_EXISTING_TARGET_FEASIBLE

    nearest = feasible[0] if feasible else None
    return _ExistingTargetFeasibility(
        minimum_viable_tp1_price=minimum_price,
        minimum_viable_tp1_distance=minimum_distance,
        minimum_viable_tp1_distance_atr=minimum_distance_atr,
        tp1_feasibility_gap=gap,
        tp1_feasibility_gap_atr=gap_atr,
        geometry_feasible_before_quality=bool(feasible),
        feasible_existing_target_count=len(feasible),
        nearest_feasible_existing_target_price=None if nearest is None else nearest[1],
        nearest_feasible_existing_target_index=None if nearest is None else nearest[0],
        no_feasible_target_reason=no_reason,
    )


def _positive_finite(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and positive")


def _non_negative_finite(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")


def _bounded_score(name: str, value: float) -> None:
    if not math.isfinite(value) or not 0.0 <= value <= 100.0:
        raise ValueError(f"{name} must be finite and between zero and 100")


__all__ = [
    "GeometryRejectionCode",
    "GeometrySafetyAssessment",
    "GeometrySafetyDiagnostics",
    "GeometrySafetyPolicy",
    "GeometrySafetyState",
    "LaneGeometryPolicy",
    "NoFeasibleTargetReason",
    "evaluate_geometry_safety",
]
