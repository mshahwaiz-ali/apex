from __future__ import annotations

from typing import cast

from apex.application.methodology_horizon_contracts import (
    HigherTimeframeAuthority,
    HoldingHorizon,
)
from apex.application.methodology_lane_horizon import LaneHorizonAssessment
from apex.application.methodology_opportunity_context import (
    infer_candidate_methodology_context,
    methodology_context_from_lane_horizon,
)
from apex.application.opportunity_portfolio import OpportunityLane
from apex.strategies.contracts import TradeCandidate
from apex.strategies.entry_status import EntryStatus


def test_context_adapter_preserves_measured_lane_and_horizon() -> None:
    assessment = LaneHorizonAssessment(
        lane=OpportunityLane.CMP_SCALP,
        holding_horizon=HoldingHorizon.STRUCTURED,
        expected_bars_to_target=18,
        current_at_cmp=True,
        reasons=("measured current structured setup",),
    )

    context = methodology_context_from_lane_horizon(assessment)

    assert context.lane is OpportunityLane.CMP_SCALP
    assert context.holding_horizon is HoldingHorizon.STRUCTURED
    assert context.higher_timeframe_authority is HigherTimeframeAuthority.WARNING_AND_TARGET_CEILING


def test_context_adapter_keeps_runner_strict() -> None:
    assessment = LaneHorizonAssessment(
        lane=OpportunityLane.RUNNER,
        holding_horizon=HoldingHorizon.RUNNER,
        expected_bars_to_target=30,
        current_at_cmp=False,
        reasons=("validated runner",),
    )

    context = methodology_context_from_lane_horizon(assessment)

    assert context.lane is OpportunityLane.RUNNER
    assert context.holding_horizon is HoldingHorizon.RUNNER
    assert context.higher_timeframe_authority is HigherTimeframeAuthority.STRICT


def test_context_adapter_keeps_nearby_structured_contextual() -> None:
    assessment = LaneHorizonAssessment(
        lane=OpportunityLane.NEARBY_STRUCTURED,
        holding_horizon=HoldingHorizon.STRUCTURED,
        expected_bars_to_target=14,
        current_at_cmp=False,
        reasons=("entry remains away from CMP",),
    )

    context = methodology_context_from_lane_horizon(assessment)

    assert context.higher_timeframe_authority is HigherTimeframeAuthority.CONTEXTUAL_PENALTY


def test_candidate_context_prefers_measured_assessment() -> None:
    assessment = LaneHorizonAssessment(
        lane=OpportunityLane.CMP_SCALP,
        holding_horizon=HoldingHorizon.STRUCTURED,
        expected_bars_to_target=18,
        current_at_cmp=True,
        reasons=("measured current structured setup",),
    )

    context = infer_candidate_methodology_context(
        cast(TradeCandidate, object()),
        entry_status=EntryStatus.READY_NOW,
        lane_horizon=assessment,
    )

    assert context.lane is OpportunityLane.CMP_SCALP
    assert context.holding_horizon is HoldingHorizon.STRUCTURED
    assert context.higher_timeframe_authority is HigherTimeframeAuthority.WARNING_AND_TARGET_CEILING
