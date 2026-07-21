from __future__ import annotations

import pytest

from apex.application.opportunity_portfolio import OpportunityLane
from apex.scoring.quality_decomposition import (
    CalibrationMetadata,
    ConfidenceSemantics,
    QualityComponents,
    calculate_overall_quality,
    quality_weights_for_lane,
)


def _components(**overrides: float) -> QualityComponents:
    values = {
        "pattern_confidence": 80.0,
        "directional_alignment": 80.0,
        "setup_quality": 80.0,
        "execution_quality": 80.0,
        "reward_quality": 80.0,
        "timing_quality": 80.0,
        "data_confidence": 80.0,
    }
    values.update(overrides)
    return QualityComponents(**values)


def test_lane_weights_sum_to_one() -> None:
    for lane in OpportunityLane:
        assert sum(quality_weights_for_lane(lane).values()) == pytest.approx(1.0)


def test_high_setup_low_execution_remains_visible() -> None:
    components = _components(setup_quality=95.0, execution_quality=20.0)
    result = calculate_overall_quality(
        lane=OpportunityLane.CMP_SCALP,
        components=components,
    )
    assert result.components.setup_quality == pytest.approx(95.0)
    assert result.components.execution_quality == pytest.approx(20.0)
    assert result.overall_trade_quality < 80.0


def test_medium_confidence_high_geometry_remains_independent() -> None:
    components = _components(
        pattern_confidence=55.0,
        setup_quality=88.0,
        execution_quality=92.0,
        reward_quality=90.0,
    )
    result = calculate_overall_quality(
        lane=OpportunityLane.NEARBY_STRUCTURED,
        components=components,
    )
    assert result.components.pattern_confidence == pytest.approx(55.0)
    assert result.components.execution_quality == pytest.approx(92.0)
    assert result.components.reward_quality == pytest.approx(90.0)


def test_high_alignment_poor_reward_is_not_hidden() -> None:
    components = _components(
        directional_alignment=98.0,
        reward_quality=15.0,
    )
    result = calculate_overall_quality(
        lane=OpportunityLane.RUNNER,
        components=components,
    )
    assert result.components.directional_alignment == pytest.approx(98.0)
    assert result.components.reward_quality == pytest.approx(15.0)
    assert result.overall_trade_quality < 80.0


def test_missing_data_lowers_data_confidence_only() -> None:
    baseline = _components()
    degraded = _components(data_confidence=30.0)
    baseline_result = calculate_overall_quality(
        lane=OpportunityLane.DEVELOPING,
        components=baseline,
    )
    degraded_result = calculate_overall_quality(
        lane=OpportunityLane.DEVELOPING,
        components=degraded,
    )
    assert degraded_result.components.setup_quality == baseline_result.components.setup_quality
    assert (
        degraded_result.components.execution_quality == baseline_result.components.execution_quality
    )
    assert degraded_result.components.data_confidence == pytest.approx(30.0)
    assert degraded_result.overall_trade_quality < baseline_result.overall_trade_quality


def test_overall_score_never_overwrites_components() -> None:
    components = _components(
        setup_quality=91.0,
        execution_quality=42.0,
        reward_quality=73.0,
    )
    result = calculate_overall_quality(
        lane=OpportunityLane.CONFIRMATION_SCALP,
        components=components,
    )
    assert result.components is components
    assert result.components.setup_quality == pytest.approx(91.0)
    assert result.components.execution_quality == pytest.approx(42.0)
    assert result.components.reward_quality == pytest.approx(73.0)


def test_uncalibrated_pattern_confidence_is_evidence_strength() -> None:
    result = calculate_overall_quality(
        lane=OpportunityLane.CMP_SCALP,
        components=_components(),
    )
    assert result.confidence_semantics is ConfidenceSemantics.EVIDENCE_STRENGTH
    assert result.calibration.calibrated is False


def test_calibrated_probability_requires_metadata() -> None:
    result = calculate_overall_quality(
        lane=OpportunityLane.CMP_SCALP,
        components=_components(),
        calibration=CalibrationMetadata(
            calibrated=True,
            method="isotonic",
            sample_size=2500,
            calibration_window="2025-01_to_2026-06",
            version="v1",
        ),
    )
    assert result.confidence_semantics is ConfidenceSemantics.CALIBRATED_PROBABILITY
    assert result.calibration.sample_size == 2500


def test_uncalibrated_metadata_rejects_probability_details() -> None:
    with pytest.raises(ValueError, match="uncalibrated metadata"):
        CalibrationMetadata(calibrated=False, method="isotonic")
