from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import cast

import pytest
from tests.unit.strategies.test_candidate_execution_quality import _candidate

from apex.application.opportunity_portfolio import OpportunityLane
from apex.domain.methodology_contracts import ScoreDimensions
from apex.scoring.candidate_quality_components import (
    attach_candidate_quality_components,
    attach_candidate_quality_components_for_candidate,
    derive_candidate_quality_components,
    resolve_candidate_quality_lane,
)
from apex.strategies.context import StrategyContext
from apex.strategies.contracts import TradeCandidate


def _context(*, confidence: float = 1.0, stale: bool = False) -> StrategyContext:
    return cast(
        StrategyContext,
        SimpleNamespace(
            decision_frame=SimpleNamespace(
                data_confidence=confidence,
                is_stale=stale,
            )
        ),
    )


def _with_dimensions(
    candidate: TradeCandidate,
    **values: float | None,
) -> TradeCandidate:
    return replace(
        candidate,
        score_dimensions=replace(candidate.score_dimensions, **values),
    )


def test_execution_quality_is_preserved_as_authoritative_component() -> None:
    candidate = _with_dimensions(_candidate(), execution_quality=37.0)

    derived = derive_candidate_quality_components(
        candidate=candidate,
        context=_context(),
        lane=OpportunityLane.CMP_SCALP,
    )

    assert derived.components.execution_quality == pytest.approx(37.0)
    assert derived.sources["execution_quality"] == "score_dimensions.execution_quality"


def test_missing_execution_quality_is_rejected_instead_of_fabricated() -> None:
    candidate = replace(_candidate(), score_dimensions=ScoreDimensions())

    with pytest.raises(ValueError, match="must be attached"):
        derive_candidate_quality_components(
            candidate=candidate,
            context=_context(),
            lane=OpportunityLane.CMP_SCALP,
        )


def test_existing_independent_dimensions_are_not_overwritten() -> None:
    candidate = _with_dimensions(
        _candidate(),
        pattern_confidence=61.0,
        directional_alignment=72.0,
        setup_quality=83.0,
        execution_quality=44.0,
        reward_quality=95.0,
        timing_quality=36.0,
        data_confidence=77.0,
    )

    derived = derive_candidate_quality_components(
        candidate=candidate,
        context=_context(confidence=0.2, stale=True),
        lane=OpportunityLane.NEARBY_STRUCTURED,
    )

    assert derived.components.pattern_confidence == pytest.approx(61.0)
    assert derived.components.directional_alignment == pytest.approx(72.0)
    assert derived.components.setup_quality == pytest.approx(83.0)
    assert derived.components.execution_quality == pytest.approx(44.0)
    assert derived.components.reward_quality == pytest.approx(95.0)
    assert derived.components.timing_quality == pytest.approx(36.0)
    assert derived.components.data_confidence == pytest.approx(77.0)


def test_fallback_components_use_canonical_candidate_metrics() -> None:
    candidate = _with_dimensions(_candidate(), execution_quality=88.0)

    derived = derive_candidate_quality_components(
        candidate=candidate,
        context=_context(confidence=0.9),
        lane=OpportunityLane.CONFIRMATION_SCALP,
    )

    assert derived.components.directional_alignment == pytest.approx(
        candidate.quality.trend_alignment * 100.0
    )
    assert derived.components.reward_quality == pytest.approx(
        candidate.quality.target_space_quality * 100.0
    )
    assert derived.components.data_confidence == pytest.approx(90.0)


def test_stale_context_caps_only_data_confidence() -> None:
    candidate = _with_dimensions(_candidate(), execution_quality=86.0)

    fresh = derive_candidate_quality_components(
        candidate=candidate,
        context=_context(confidence=0.9),
        lane=OpportunityLane.DEVELOPING,
    )
    stale = derive_candidate_quality_components(
        candidate=candidate,
        context=_context(confidence=0.9, stale=True),
        lane=OpportunityLane.DEVELOPING,
    )

    assert stale.components.data_confidence == pytest.approx(25.0)
    assert stale.components.execution_quality == fresh.components.execution_quality
    assert stale.components.setup_quality == fresh.components.setup_quality
    assert stale.overall.overall_trade_quality < fresh.overall.overall_trade_quality


def test_lane_changes_overall_weighting_not_raw_components() -> None:
    candidate = _with_dimensions(
        _candidate(),
        setup_quality=92.0,
        execution_quality=31.0,
        reward_quality=84.0,
    )

    scalp = derive_candidate_quality_components(
        candidate=candidate,
        context=_context(),
        lane=OpportunityLane.CMP_SCALP,
    )
    runner = derive_candidate_quality_components(
        candidate=candidate,
        context=_context(),
        lane=OpportunityLane.RUNNER,
    )

    assert scalp.components == runner.components
    assert scalp.overall.overall_trade_quality != runner.overall.overall_trade_quality


def test_sources_explain_every_component_and_overall() -> None:
    candidate = _with_dimensions(_candidate(), execution_quality=81.0)

    derived = derive_candidate_quality_components(
        candidate=candidate,
        context=_context(),
        lane=OpportunityLane.PULLBACK_SCALP,
    )

    assert set(derived.sources) == {
        "pattern_confidence",
        "directional_alignment",
        "setup_quality",
        "execution_quality",
        "reward_quality",
        "timing_quality",
        "data_confidence",
        "overall_trade_quality",
    }


def test_attachment_populates_all_score_dimensions_without_changing_rank_score() -> None:
    candidate = _with_dimensions(
        _candidate(),
        execution_quality=62.0,
        rank_score=88.0,
    )

    attached = attach_candidate_quality_components(
        candidate=candidate,
        context=_context(confidence=0.9),
        lane=OpportunityLane.CMP_SCALP,
    )

    dimensions = attached.score_dimensions
    assert dimensions.pattern_confidence is not None
    assert dimensions.directional_alignment is not None
    assert dimensions.setup_quality is not None
    assert dimensions.execution_quality == pytest.approx(62.0)
    assert dimensions.reward_quality is not None
    assert dimensions.timing_quality is not None
    assert dimensions.data_confidence == pytest.approx(90.0)
    assert dimensions.overall_trade_quality is not None
    assert dimensions.rank_score == pytest.approx(88.0)


def test_attachment_is_immutable_and_preserves_authoritative_execution_quality() -> None:
    candidate = _with_dimensions(_candidate(), execution_quality=41.0)

    attached = attach_candidate_quality_components(
        candidate=candidate,
        context=_context(),
        lane=OpportunityLane.NEARBY_STRUCTURED,
    )

    assert attached is not candidate
    assert candidate.score_dimensions.setup_quality is None
    assert attached.score_dimensions.execution_quality == pytest.approx(41.0)


def test_attachment_marks_shadow_only_semantics() -> None:
    candidate = _with_dimensions(_candidate(), execution_quality=75.0)

    attached = attach_candidate_quality_components(
        candidate=candidate,
        context=_context(),
        lane=OpportunityLane.RUNNER,
    )

    assert attached.metadata["quality_decomposition_lane"] == "runner"
    assert attached.metadata["quality_confidence_semantics"] == "evidence_strength"
    assert attached.metadata["quality_calibrated_probability"] is False
    assert attached.metadata["quality_decomposition_shadow_only"] is True


def test_attachment_records_component_sources() -> None:
    candidate = _with_dimensions(
        _candidate(),
        setup_quality=93.0,
        execution_quality=52.0,
    )

    attached = attach_candidate_quality_components(
        candidate=candidate,
        context=_context(),
        lane=OpportunityLane.PULLBACK_SCALP,
    )

    sources = attached.metadata["quality_component_sources"]
    assert isinstance(sources, str)
    assert "setup_quality=score_dimensions.setup_quality" in sources
    assert "execution_quality=score_dimensions.execution_quality" in sources
    assert "overall_trade_quality=lane_weights:pullback_scalp" in sources


def test_attachment_does_not_write_probability_without_calibration() -> None:
    candidate = _with_dimensions(_candidate(), execution_quality=79.0)

    attached = attach_candidate_quality_components(
        candidate=candidate,
        context=_context(),
        lane=OpportunityLane.CONFIRMATION_SCALP,
    )

    assert attached.metadata["quality_confidence_semantics"] == "evidence_strength"
    assert attached.metadata["quality_calibrated_probability"] is False


def test_lane_resolution_uses_canonical_measurement_when_available() -> None:
    candidate = _with_dimensions(_candidate(), execution_quality=80.0)
    candidate = replace(
        candidate,
        metadata={
            **candidate.metadata,
            "execution_timeframe": "5m",
            "setup_timeframe": "5m",
            "invalidation_timeframe": "5m",
            "target_timeframe": "5m",
            "expected_bars_to_target": 4,
            "decision_atr": 2.0,
            "lifecycle_model": "scalp",
        },
    )

    resolution = resolve_candidate_quality_lane(candidate=candidate)

    assert resolution.lane is OpportunityLane.CMP_SCALP
    assert resolution.source == "canonical_lane_horizon_assessment"
    assert resolution.missing_measurements == ()


def test_lane_resolution_is_conservative_when_measurement_is_missing() -> None:
    candidate = _with_dimensions(_candidate(), execution_quality=80.0)

    resolution = resolve_candidate_quality_lane(candidate=candidate)

    assert resolution.lane is OpportunityLane.DEVELOPING
    assert resolution.source == "lane_horizon_measurement_unavailable"
    assert "execution_timeframe" in resolution.missing_measurements


def test_shadow_pipeline_attachment_records_lane_resolution() -> None:
    candidate = _with_dimensions(_candidate(), execution_quality=74.0)

    attached = attach_candidate_quality_components_for_candidate(
        candidate=candidate,
        context=_context(),
    )

    assert attached.score_dimensions.overall_trade_quality is not None
    assert attached.metadata["quality_decomposition_lane"] == "developing"
    assert (
        attached.metadata["quality_lane_resolution_source"]
        == "lane_horizon_measurement_unavailable"
    )
    assert attached.metadata["quality_decomposition_shadow_only"] is True
