from __future__ import annotations

from dataclasses import replace

from tests.unit.strategies.test_candidate_execution_quality import _candidate

from apex.application.discovery_contracts import (
    ManagementPolicyType,
    TakeProfit,
    TargetRole,
)
from apex.application.discovery_setup import (
    _management_policies,
    _runner_qualification,
)
from apex.domain.methodology_contracts import (
    ContinuationState,
    HoldingHorizon,
    LayeredStateSnapshot,
    RelationshipSeverity,
    TimeframeRelationship,
)
from apex.strategies.contracts import TargetType


def _target(*, runner: bool) -> TakeProfit:
    return TakeProfit(
        label="TP2",
        price=106.0,
        reward=6.0,
        risk_reward=3.0,
        rationale=("strategy expansion target",),
        partial_close_pct=25.0,
        target_type=TargetType.EXPANSION,
        target_role=TargetRole.EXTENSION_CANDIDATE,
        runner_qualified=runner,
    )


def _candidate_with(
    *,
    relationship: TimeframeRelationship,
    evidence: bool = True,
):
    candidate = _candidate()
    return replace(
        candidate,
        layered_state=LayeredStateSnapshot(
            timeframe_relationship=relationship,
            relationship_severity=RelationshipSeverity.NONE,
            continuation_state=ContinuationState.FRESH_CONTINUATION,
            holding_horizon=HoldingHorizon.MULTI_HOUR,
        ),
        metadata={
            **candidate.metadata,
            "continuation_evidence_complete": evidence,
        },
    )


def test_runner_qualification_returns_explicit_denial_reason() -> None:
    qualified, reason = _runner_qualification(
        _candidate_with(relationship=TimeframeRelationship.DIRECT_STRUCTURAL_OPPOSITION)
    )
    assert qualified is False
    assert "forbids runner" in reason


def test_runner_qualification_returns_explicit_success_reason() -> None:
    qualified, reason = _runner_qualification(
        _candidate_with(relationship=TimeframeRelationship.WITH_TREND)
    )
    assert qualified is True
    assert "supports runner management" in reason


def test_qualified_runner_uses_structural_trailing_policy() -> None:
    policies = _management_policies((_target(runner=True),), runner_qualified=True)
    trailing = next(item for item in policies if item.kind is ManagementPolicyType.TRAILING)
    assert "qualified runner" in trailing.action
    assert "continuation potential" in trailing.rationale[0]


def test_denied_runner_keeps_targets_but_disables_runner_retention() -> None:
    policies = _management_policies((_target(runner=False),), runner_qualified=False)
    trailing = next(item for item in policies if item.kind is ManagementPolicyType.TRAILING)
    assert trailing.trigger == "TP2 reached"
    assert "do not retain a runner" in trailing.action
    assert "not earned" in trailing.rationale[0]


def test_runner_lifecycle_always_keeps_breakeven_time_and_failure_policies() -> None:
    policies = _management_policies((_target(runner=True),), runner_qualified=True)
    kinds = {policy.kind for policy in policies}
    assert ManagementPolicyType.BREAKEVEN in kinds
    assert ManagementPolicyType.TIME_EXIT in kinds
    assert ManagementPolicyType.MOMENTUM_FAILURE in kinds
