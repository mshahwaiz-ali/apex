from __future__ import annotations

from dataclasses import replace

import pytest
from tests.unit.strategies.test_candidate_execution_quality import _candidate

from apex.application.discovery_setup import (
    _partial_close_percentages,
    _runner_is_qualified,
)
from apex.domain.methodology_contracts import (
    ContinuationState,
    HoldingHorizon,
    LayeredStateSnapshot,
    RelationshipSeverity,
    TimeframeRelationship,
)


def _with_state(
    *,
    relationship: TimeframeRelationship,
    severity: RelationshipSeverity = RelationshipSeverity.NONE,
    continuation: ContinuationState = ContinuationState.FRESH_CONTINUATION,
    horizon: HoldingHorizon = HoldingHorizon.MULTI_HOUR,
    evidence_complete: bool = True,
):
    candidate = _candidate()
    return replace(
        candidate,
        layered_state=LayeredStateSnapshot(
            timeframe_relationship=relationship,
            relationship_severity=severity,
            continuation_state=continuation,
            holding_horizon=horizon,
        ),
        metadata={
            **candidate.metadata,
            "continuation_evidence_complete": evidence_complete,
        },
    )


def test_partial_allocations_are_exact_for_one_to_three_targets() -> None:
    assert _partial_close_percentages(1) == (100.0,)
    assert _partial_close_percentages(2) == (50.0, 50.0)
    assert _partial_close_percentages(3) == (40.0, 35.0, 25.0)
    assert sum(_partial_close_percentages(3)) == 100.0


def test_partial_allocation_rejects_more_than_three_targets() -> None:
    with pytest.raises(ValueError, match="at most three targets"):
        _partial_close_percentages(4)


def test_runner_is_denied_under_direct_htf_opposition() -> None:
    candidate = _with_state(relationship=TimeframeRelationship.DIRECT_STRUCTURAL_OPPOSITION)
    assert _runner_is_qualified(candidate) is False


def test_runner_is_denied_for_countertrend_scalp() -> None:
    candidate = _with_state(relationship=TimeframeRelationship.COUNTERTREND_SCALP)
    assert _runner_is_qualified(candidate) is False


def test_runner_requires_fresh_continuation() -> None:
    candidate = _with_state(
        relationship=TimeframeRelationship.WITH_TREND,
        continuation=ContinuationState.MATURE_CONTINUATION,
    )
    assert _runner_is_qualified(candidate) is False


def test_runner_requires_explicit_continuation_evidence() -> None:
    candidate = _with_state(
        relationship=TimeframeRelationship.WITH_TREND,
        evidence_complete=False,
    )
    assert _runner_is_qualified(candidate) is False


def test_runner_requires_multi_hour_or_longer_horizon() -> None:
    candidate = _with_state(
        relationship=TimeframeRelationship.WITH_TREND,
        horizon=HoldingHorizon.SCALP,
    )
    assert _runner_is_qualified(candidate) is False


def test_runner_qualifies_only_aligned_fresh_continuation() -> None:
    candidate = _with_state(
        relationship=TimeframeRelationship.WITH_TREND,
        severity=RelationshipSeverity.NONE,
        continuation=ContinuationState.FRESH_CONTINUATION,
        horizon=HoldingHorizon.MULTI_HOUR,
        evidence_complete=True,
    )
    assert _runner_is_qualified(candidate) is True
