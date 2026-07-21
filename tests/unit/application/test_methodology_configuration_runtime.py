from __future__ import annotations

from apex.application.methodology_candidate_geometry_safety import (
    geometry_safety_policy_from_settings,
)
from apex.application.methodology_htf_consequences import HtfConsequencePolicy
from apex.application.opportunity_portfolio import OpportunityLane
from apex.application.portfolio_ranking import (
    portfolio_ranking_policy_from_settings,
)
from apex.config import MethodologySettings
from apex.strategies.execution_quality import ExecutionQualityCapPolicy


def test_geometry_policy_uses_lane_specific_methodology_settings() -> None:
    payload = MethodologySettings().model_dump()
    payload["lane_geometry"]["cmp_scalp"]["minimum_tp1_reward_to_risk"] = 1.35
    payload["lane_geometry"]["cmp_scalp"]["maximum_stop_distance_pct"] = 1.75
    payload["lane_geometry"]["cmp_scalp"]["minimum_target_quality"] = 58.0
    settings = MethodologySettings.model_validate(payload)

    policy = geometry_safety_policy_from_settings(settings)
    cmp_policy = policy.for_lane(OpportunityLane.CMP_SCALP)

    assert cmp_policy.minimum_tp1_reward_to_risk == 1.35
    assert cmp_policy.maximum_stop_distance_pct == 1.75
    assert cmp_policy.minimum_target_quality == 58.0


def test_geometry_policy_preserves_all_required_lanes() -> None:
    policy = geometry_safety_policy_from_settings(MethodologySettings())

    assert set(policy.lanes) == set(OpportunityLane)


def test_execution_cap_policy_accepts_validated_methodology_values() -> None:
    payload = MethodologySettings().model_dump()
    payload["execution_quality_caps"]["trigger_incomplete"] = 0.71
    settings = MethodologySettings.model_validate(payload)

    policy = ExecutionQualityCapPolicy(**settings.execution_quality_caps.model_dump())

    assert policy.trigger_incomplete == 0.71


def test_ranking_policy_accepts_validated_methodology_weights() -> None:
    payload = MethodologySettings().model_dump()
    payload["ranking_weights"] = {
        "execution_precedence": 0.10,
        "tp1_reward_quality": 0.30,
        "target_quality": 0.10,
        "setup_quality": 0.10,
        "execution_quality": 0.10,
        "htf_alignment": 0.10,
        "timing_quality": 0.05,
        "data_confidence": 0.05,
        "overall_trade_quality": 0.10,
    }
    settings = MethodologySettings.model_validate(payload)

    policy = portfolio_ranking_policy_from_settings(settings.ranking_weights)

    assert policy.execution_precedence == 0.10
    assert policy.tp1_reward_quality == 0.30
    assert policy.overall_trade_quality == 0.10


def test_htf_policy_accepts_validated_methodology_values() -> None:
    payload = MethodologySettings().model_dump()
    payload["htf_consequences"]["mixed_mild_target_ceiling_r"] = 3.25
    settings = MethodologySettings.model_validate(payload)

    policy = HtfConsequencePolicy(**settings.htf_consequences.model_dump())

    assert policy.mixed_mild_target_ceiling_r == 3.25
