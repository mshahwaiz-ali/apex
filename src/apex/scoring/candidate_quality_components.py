"""Derive independent quality components from canonical candidate evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

from apex.application.methodology_candidate_lane_horizon import (
    measure_candidate_lane_horizon,
)
from apex.application.opportunity_portfolio import OpportunityLane
from apex.scoring.quality_decomposition import (
    OverallQualityResult,
    QualityComponents,
    calculate_overall_quality,
)
from apex.strategies.actionability import classify_candidate_actionability
from apex.strategies.context import StrategyContext
from apex.strategies.contracts import TradeCandidate


@dataclass(frozen=True, slots=True)
class CandidateQualityComponentDerivation:
    """Auditable component derivation without collapsing independent meanings."""

    lane: OpportunityLane
    components: QualityComponents
    overall: OverallQualityResult
    sources: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", MappingProxyType(dict(self.sources)))


def derive_candidate_quality_components(
    *,
    candidate: TradeCandidate,
    context: StrategyContext,
    lane: OpportunityLane,
) -> CandidateQualityComponentDerivation:
    """Build seven independent components from canonical candidate and context data."""

    dimensions = candidate.score_dimensions
    execution_quality = dimensions.execution_quality
    if execution_quality is None:
        raise ValueError(
            "candidate execution quality must be attached before quality decomposition"
        )

    pattern_confidence, pattern_source = _dimension_or_default(
        dimensions.pattern_confidence,
        _pattern_confidence(candidate),
        "score_dimensions.pattern_confidence",
        "candidate evidence balance",
    )
    directional_alignment, directional_source = _dimension_or_default(
        dimensions.directional_alignment,
        candidate.quality.trend_alignment * 100.0,
        "score_dimensions.directional_alignment",
        "quality.trend_alignment",
    )
    setup_quality, setup_source = _dimension_or_default(
        dimensions.setup_quality,
        _setup_quality(candidate),
        "score_dimensions.setup_quality",
        "independent structure/momentum/volume/liquidity blend",
    )
    reward_quality, reward_source = _dimension_or_default(
        dimensions.reward_quality,
        candidate.quality.target_space_quality * 100.0,
        "score_dimensions.reward_quality",
        "quality.target_space_quality",
    )
    timing_quality, timing_source = _dimension_or_default(
        dimensions.timing_quality,
        _timing_quality(candidate),
        "score_dimensions.timing_quality",
        "entry location/freshness/confirmation evidence",
    )
    data_confidence, data_source = _dimension_or_default(
        dimensions.data_confidence,
        _data_confidence(context),
        "score_dimensions.data_confidence",
        "decision_frame.data_confidence and staleness",
    )

    components = QualityComponents(
        pattern_confidence=round(pattern_confidence, 4),
        directional_alignment=round(directional_alignment, 4),
        setup_quality=round(setup_quality, 4),
        execution_quality=round(execution_quality, 4),
        reward_quality=round(reward_quality, 4),
        timing_quality=round(timing_quality, 4),
        data_confidence=round(data_confidence, 4),
    )
    overall = calculate_overall_quality(
        lane=lane,
        components=components,
    )
    return CandidateQualityComponentDerivation(
        lane=lane,
        components=components,
        overall=overall,
        sources={
            "pattern_confidence": pattern_source,
            "directional_alignment": directional_source,
            "setup_quality": setup_source,
            "execution_quality": "score_dimensions.execution_quality",
            "reward_quality": reward_source,
            "timing_quality": timing_source,
            "data_confidence": data_source,
            "overall_trade_quality": f"lane_weights:{lane.value}",
        },
    )


def attach_candidate_quality_components(
    *,
    candidate: TradeCandidate,
    context: StrategyContext,
    lane: OpportunityLane,
) -> TradeCandidate:
    """Attach independent dimensions without changing ranking authority."""

    derived = derive_candidate_quality_components(
        candidate=candidate,
        context=context,
        lane=lane,
    )
    components = derived.components
    dimensions = replace(
        candidate.score_dimensions,
        pattern_confidence=components.pattern_confidence,
        directional_alignment=components.directional_alignment,
        setup_quality=components.setup_quality,
        execution_quality=components.execution_quality,
        reward_quality=components.reward_quality,
        timing_quality=components.timing_quality,
        data_confidence=components.data_confidence,
        overall_trade_quality=derived.overall.overall_trade_quality,
    )
    metadata = {
        **candidate.metadata,
        "quality_decomposition_lane": lane.value,
        "quality_confidence_semantics": derived.overall.confidence_semantics.value,
        "quality_calibrated_probability": derived.overall.calibration.calibrated,
        "quality_component_sources": " | ".join(
            f"{name}={source}" for name, source in sorted(derived.sources.items())
        ),
        "quality_decomposition_shadow_only": True,
    }
    return replace(
        candidate,
        score_dimensions=dimensions,
        metadata=metadata,
    )


@dataclass(frozen=True, slots=True)
class CandidateQualityLaneResolution:
    """Lane selected for shadow quality weighting with explicit provenance."""

    lane: OpportunityLane
    source: str
    missing_measurements: tuple[str, ...] = ()


def resolve_candidate_quality_lane(
    *,
    candidate: TradeCandidate,
) -> CandidateQualityLaneResolution:
    """Resolve the canonical measured lane or conservatively remain developing."""

    entry_status = classify_candidate_actionability(candidate)
    raw_runner_authority = candidate.metadata.get("runner_authority")
    runner_authority = raw_runner_authority if isinstance(raw_runner_authority, bool) else None
    measurement = measure_candidate_lane_horizon(
        candidate,
        entry_status=entry_status,
        runner_authority=runner_authority,
    )
    if measurement.assessment is None:
        return CandidateQualityLaneResolution(
            lane=OpportunityLane.DEVELOPING,
            source="lane_horizon_measurement_unavailable",
            missing_measurements=measurement.missing_measurements,
        )
    return CandidateQualityLaneResolution(
        lane=measurement.assessment.lane,
        source="canonical_lane_horizon_assessment",
    )


def attach_candidate_quality_components_for_candidate(
    *,
    candidate: TradeCandidate,
    context: StrategyContext,
) -> TradeCandidate:
    """Attach shadow decomposition using the canonical measured candidate lane."""

    resolution = resolve_candidate_quality_lane(candidate=candidate)
    attached = attach_candidate_quality_components(
        candidate=candidate,
        context=context,
        lane=resolution.lane,
    )
    metadata = {
        **attached.metadata,
        "quality_lane_resolution_source": resolution.source,
        "quality_lane_missing_measurements": ",".join(resolution.missing_measurements),
    }
    return replace(attached, metadata=metadata)


def _dimension_or_default(
    dimension: float | None,
    fallback: float,
    dimension_source: str,
    fallback_source: str,
) -> tuple[float, str]:
    if dimension is not None:
        return dimension, dimension_source
    return fallback, fallback_source


def _pattern_confidence(candidate: TradeCandidate) -> float:
    support = len(candidate.evidence.supporting)
    contradictions = len(candidate.evidence.contradictions)
    warnings = len(candidate.evidence.warnings)
    total = support + contradictions + warnings
    if total == 0:
        return 50.0
    raw = (support + warnings * 0.25) / total
    return _bounded(raw * 100.0)


def _setup_quality(candidate: TradeCandidate) -> float:
    quality = candidate.quality
    value = 100.0 * (
        quality.structure_quality * 0.35
        + quality.momentum_quality * 0.20
        + quality.volume_quality * 0.15
        + quality.liquidity_quality * 0.15
        + quality.trend_alignment * 0.15
    )
    return _bounded(value)


def _timing_quality(candidate: TradeCandidate) -> float:
    quality = candidate.entry.location_quality * 100.0
    quality -= candidate.quality.extension_penalty * 30.0
    if candidate.entry.is_extended:
        quality -= 15.0
    if candidate.provisional:
        quality -= 15.0
    if candidate.metadata.get("entry_confirmation_complete") is False:
        quality -= 10.0
    return _bounded(quality)


def _data_confidence(context: StrategyContext) -> float:
    frame = context.decision_frame
    confidence = frame.data_confidence * 100.0
    if frame.is_stale:
        confidence = min(confidence, 25.0)
    return _bounded(confidence)


def _bounded(value: float) -> float:
    return max(0.0, min(100.0, value))


__all__ = [
    "CandidateQualityComponentDerivation",
    "CandidateQualityLaneResolution",
    "attach_candidate_quality_components",
    "attach_candidate_quality_components_for_candidate",
    "derive_candidate_quality_components",
    "resolve_candidate_quality_lane",
]
