"""Geometry- and lifecycle-aware lane and holding-horizon derivation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.application.methodology_horizon_contracts import HoldingHorizon
from apex.application.opportunity_portfolio import OpportunityLane
from apex.strategies.strategy_types import StrategyType


class PriceEntryRelation(StrEnum):
    INSIDE_ZONE = "inside_zone"
    NEAR_ZONE = "near_zone"
    AWAY_FROM_ZONE = "away_from_zone"
    BEYOND_MAX_CHASE = "beyond_max_chase"


class TriggerState(StrEnum):
    READY = "ready"
    CONFIRMATION_REQUIRED = "confirmation_required"
    PULLBACK_REQUIRED = "pullback_required"
    DEVELOPING = "developing"
    INVALID = "invalid"


class LifecycleModel(StrEnum):
    MICRO_SCALP = "micro_scalp"
    SCALP = "scalp"
    STRUCTURED = "structured"
    RUNNER = "runner"
    DEVELOPING = "developing"


@dataclass(frozen=True, slots=True)
class LaneHorizonInput:
    strategy: StrategyType
    execution_timeframe_minutes: int
    setup_timeframe_minutes: int
    invalidation_timeframe_minutes: int
    target_timeframe_minutes: int
    atr_normalized_target_distance: float
    expected_bars_to_target: int
    price_entry_relation: PriceEntryRelation
    trigger_state: TriggerState
    lifecycle_model: LifecycleModel
    runner_authority: bool = False

    def __post_init__(self) -> None:
        for name in (
            "execution_timeframe_minutes",
            "setup_timeframe_minutes",
            "invalidation_timeframe_minutes",
            "target_timeframe_minutes",
            "expected_bars_to_target",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.atr_normalized_target_distance <= 0.0:
            raise ValueError("atr_normalized_target_distance must be positive")


@dataclass(frozen=True, slots=True)
class LaneHorizonAssessment:
    lane: OpportunityLane
    holding_horizon: HoldingHorizon
    expected_bars_to_target: int
    current_at_cmp: bool
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.reasons:
            raise ValueError("lane and horizon assessment requires reasons")
        if self.expected_bars_to_target <= 0:
            raise ValueError("expected bars to target must be positive")


def _derive_horizon(value: LaneHorizonInput) -> HoldingHorizon:
    if value.lifecycle_model is LifecycleModel.RUNNER:
        return HoldingHorizon.RUNNER
    if value.lifecycle_model is LifecycleModel.DEVELOPING:
        return HoldingHorizon.STRUCTURED

    broad_target = value.target_timeframe_minutes >= 30
    broad_setup = value.setup_timeframe_minutes >= 15
    long_path = value.expected_bars_to_target > 12
    wide_target = value.atr_normalized_target_distance >= 2.0

    if broad_target or (broad_setup and long_path) or wide_target:
        return HoldingHorizon.STRUCTURED
    if value.expected_bars_to_target > 6:
        return HoldingHorizon.SHORT
    return HoldingHorizon.SCALP


def classify_lane_and_horizon(
    value: LaneHorizonInput,
) -> LaneHorizonAssessment:
    horizon = _derive_horizon(value)
    at_cmp = value.price_entry_relation is PriceEntryRelation.INSIDE_ZONE

    if value.trigger_state is TriggerState.INVALID:
        return LaneHorizonAssessment(
            lane=OpportunityLane.DEVELOPING,
            holding_horizon=horizon,
            expected_bars_to_target=value.expected_bars_to_target,
            current_at_cmp=at_cmp,
            reasons=("invalid trigger cannot be classified as an executable lane",),
        )

    if value.lifecycle_model is LifecycleModel.RUNNER:
        if not value.runner_authority:
            return LaneHorizonAssessment(
                lane=OpportunityLane.DEVELOPING,
                holding_horizon=HoldingHorizon.STRUCTURED,
                expected_bars_to_target=value.expected_bars_to_target,
                current_at_cmp=at_cmp,
                reasons=("runner lifecycle lacks broader structural authority",),
            )
        return LaneHorizonAssessment(
            lane=OpportunityLane.RUNNER,
            holding_horizon=HoldingHorizon.RUNNER,
            expected_bars_to_target=value.expected_bars_to_target,
            current_at_cmp=at_cmp,
            reasons=("runner lifecycle is supported by broader structural authority",),
        )

    if value.trigger_state is TriggerState.DEVELOPING:
        return LaneHorizonAssessment(
            lane=OpportunityLane.DEVELOPING,
            holding_horizon=horizon,
            expected_bars_to_target=value.expected_bars_to_target,
            current_at_cmp=at_cmp,
            reasons=("setup lifecycle is still developing",),
        )

    if at_cmp:
        lane = (
            OpportunityLane.CONFIRMATION_SCALP
            if value.trigger_state is TriggerState.CONFIRMATION_REQUIRED
            else OpportunityLane.CMP_SCALP
        )
        return LaneHorizonAssessment(
            lane=lane,
            holding_horizon=horizon,
            expected_bars_to_target=value.expected_bars_to_target,
            current_at_cmp=True,
            reasons=(
                "current price is inside the valid entry zone; nearby "
                "classification is not permitted",
            ),
        )

    if value.trigger_state is TriggerState.PULLBACK_REQUIRED:
        lane = (
            OpportunityLane.PULLBACK_SCALP
            if horizon in {HoldingHorizon.SCALP, HoldingHorizon.SHORT}
            else OpportunityLane.NEARBY_STRUCTURED
        )
        return LaneHorizonAssessment(
            lane=lane,
            holding_horizon=horizon,
            expected_bars_to_target=value.expected_bars_to_target,
            current_at_cmp=False,
            reasons=("entry remains conditional on a pullback away from current price",),
        )

    if value.price_entry_relation in {
        PriceEntryRelation.NEAR_ZONE,
        PriceEntryRelation.AWAY_FROM_ZONE,
    }:
        return LaneHorizonAssessment(
            lane=OpportunityLane.NEARBY_STRUCTURED,
            holding_horizon=horizon,
            expected_bars_to_target=value.expected_bars_to_target,
            current_at_cmp=False,
            reasons=("valid entry geometry remains away from current price",),
        )

    return LaneHorizonAssessment(
        lane=OpportunityLane.DEVELOPING,
        holding_horizon=horizon,
        expected_bars_to_target=value.expected_bars_to_target,
        current_at_cmp=False,
        reasons=("current price is beyond maximum chase tolerance",),
    )


def lane_horizon_payload(
    assessment: LaneHorizonAssessment,
) -> dict[str, object]:
    return {
        "lane": assessment.lane.value,
        "holding_horizon": assessment.holding_horizon.value,
        "expected_bars_to_target": assessment.expected_bars_to_target,
        "current_at_cmp": assessment.current_at_cmp,
        "reasons": list(assessment.reasons),
    }


__all__ = [
    "LaneHorizonAssessment",
    "LaneHorizonInput",
    "LifecycleModel",
    "PriceEntryRelation",
    "TriggerState",
    "classify_lane_and_horizon",
    "lane_horizon_payload",
]
