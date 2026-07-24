from apex.application.methodology_candidate_routing import (
    _htf_assessment_from_layered_state,
    _opposite_continuation_risk_requires_no_trade,
)
from apex.domain.methodology_contracts import (
    LayeredStateSnapshot,
    RelationshipSeverity,
    TimeframeRelationship,
)


def _state(
    relationship: TimeframeRelationship,
    severity: RelationshipSeverity,
) -> LayeredStateSnapshot:
    return LayeredStateSnapshot(
        timeframe_relationship=relationship,
        relationship_severity=severity,
    )


def test_strong_countertrend_risk_is_no_trade() -> None:
    assessment = _htf_assessment_from_layered_state(
        _state(
            TimeframeRelationship.COUNTERTREND_SCALP,
            RelationshipSeverity.STRONG,
        )
    )
    assert assessment is not None
    assert assessment.hard_reject is True
    assert "opposite-continuation risk" in assessment.reasons[0]


def test_critical_reversal_attempt_risk_is_no_trade() -> None:
    assessment = _htf_assessment_from_layered_state(
        _state(
            TimeframeRelationship.REVERSAL_ATTEMPT,
            RelationshipSeverity.CRITICAL,
        )
    )
    assert assessment is not None
    assert assessment.hard_reject is True


def test_moderate_countertrend_remains_conditional_scalp() -> None:
    assessment = _htf_assessment_from_layered_state(
        _state(
            TimeframeRelationship.COUNTERTREND_SCALP,
            RelationshipSeverity.MODERATE,
        )
    )
    assert assessment is not None
    assert assessment.hard_reject is False
    assert assessment.confirmation_required is True


def test_with_trend_is_never_rejected_by_opposite_continuation_gate() -> None:
    assert not _opposite_continuation_risk_requires_no_trade(
        TimeframeRelationship.WITH_TREND,
        RelationshipSeverity.CRITICAL,
    )
