from __future__ import annotations

import json

import pytest

from apex.domain.methodology_contracts import (
    ContextState,
    ContinuationState,
    ExecutionState,
    HoldingHorizon,
    LayeredStateSnapshot,
    RelationshipSeverity,
    RiskCondition,
    ScoreDimensions,
    SetupState,
    StructuralBias,
    TimeframeRelationship,
)


def test_layered_state_round_trip_is_deterministic() -> None:
    snapshot = LayeredStateSnapshot(
        execution_state=ExecutionState.CLEAN,
        setup_state=SetupState.PULLBACK,
        context_state=ContextState.TRENDING_UP,
        structural_bias=StructuralBias.BULLISH,
        risk_condition=RiskCondition.ELEVATED,
        timeframe_relationship=TimeframeRelationship.WITH_TREND,
        relationship_severity=RelationshipSeverity.MILD,
        holding_horizon=HoldingHorizon.INTRADAY,
        continuation_state=ContinuationState.FRESH_CONTINUATION,
    )

    encoded = json.loads(json.dumps(snapshot.to_dict()))

    assert LayeredStateSnapshot.from_dict(encoded) == snapshot


def test_layered_state_defaults_are_unavailable_not_inferred() -> None:
    snapshot = LayeredStateSnapshot.from_dict({})

    assert set(snapshot.to_dict().values()) == {"unavailable"}


def test_enum_labels_are_stable_and_human_readable() -> None:
    assert TimeframeRelationship.COUNTERTREND_SCALP.label == "Countertrend scalp"
    assert ContinuationState.EXHAUSTION_WARNING.label == "Exhaustion warning"
    assert ExecutionState.labels()["chaotic"] == "Chaotic"


def test_score_dimensions_preserve_absent_values_as_none() -> None:
    scores = ScoreDimensions(setup_quality=81.0, execution_quality=43.0)

    payload = scores.to_dict()

    assert payload["pattern_confidence"] is None
    assert payload["reward_quality"] is None
    assert payload["setup_quality"] == 81.0
    assert payload["execution_quality"] == 43.0
    assert ScoreDimensions.from_dict(payload) == scores


def test_score_dimensions_do_not_copy_semantics() -> None:
    scores = ScoreDimensions(
        pattern_confidence=76.0,
        setup_quality=81.0,
        execution_quality=43.0,
        reward_quality=69.0,
        overall_trade_quality=64.0,
    )

    assert (
        len(
            {
                scores.pattern_confidence,
                scores.setup_quality,
                scores.execution_quality,
                scores.reward_quality,
                scores.overall_trade_quality,
            }
        )
        == 5
    )


@pytest.mark.parametrize("value", [-0.01, 100.01, float("inf"), float("nan")])
def test_score_dimensions_reject_invalid_values(value: float) -> None:
    with pytest.raises(ValueError):
        ScoreDimensions(pattern_confidence=value)


def test_holding_horizon_has_stable_operator_labels() -> None:
    assert HoldingHorizon.MICRO_SCALP.label == "Micro scalp"
    assert HoldingHorizon.MULTI_HOUR.label == "Multi-hour"
    assert HoldingHorizon.RUNNER.value == "runner"


@pytest.mark.parametrize(
    "enum_type",
    [
        ExecutionState,
        SetupState,
        ContextState,
        StructuralBias,
        RiskCondition,
        TimeframeRelationship,
        RelationshipSeverity,
        HoldingHorizon,
        ContinuationState,
    ],
)
def test_every_methodology_enum_serializes_deterministically(
    enum_type: type,
) -> None:
    for member in enum_type:
        assert enum_type(member.value) is member
        assert isinstance(member.label, str)
        assert member.label.strip()
        assert enum_type.labels()[member.value] == member.label


def test_snapshot_json_shape_is_stable() -> None:
    payload = LayeredStateSnapshot().to_dict()

    assert tuple(payload) == (
        "execution_state",
        "setup_state",
        "context_state",
        "structural_bias",
        "risk_condition",
        "timeframe_relationship",
        "relationship_severity",
        "holding_horizon",
        "continuation_state",
    )
    assert LayeredStateSnapshot.from_dict(payload).to_dict() == payload


def test_score_json_shape_is_stable_and_semantically_distinct() -> None:
    payload = ScoreDimensions().to_dict()

    assert tuple(payload) == (
        "pattern_confidence",
        "directional_alignment",
        "setup_quality",
        "execution_quality",
        "reward_quality",
        "timing_quality",
        "data_confidence",
        "overall_trade_quality",
        "rank_score",
    )
    assert set(payload.values()) == {None}
