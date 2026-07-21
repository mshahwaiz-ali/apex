"""Deterministic recommendation ranking for retained portfolio opportunities.

Ranking is downstream of hard eligibility and retention. It never promotes an
invalid setup, replaces a methodology gate, or fabricates unavailable evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from apex.application.discovery_contracts import DiscoverySetup
from apex.domain.methodology_contracts import (
    RelationshipSeverity,
    TimeframeRelationship,
)
from apex.strategies.entry_status import EntryStatus


@dataclass(frozen=True, slots=True)
class PortfolioRankComponents:
    """Visible inputs used to order hard-valid retained opportunities."""

    execution_precedence: float
    tp1_reward_quality: float
    target_quality: float | None
    setup_quality: float | None
    execution_quality: float | None
    htf_alignment: float | None
    timing_quality: float | None
    data_confidence: float | None
    overall_trade_quality: float | None
    rank_score: float

    def to_dict(self) -> dict[str, float | None]:
        return {
            "execution_precedence": self.execution_precedence,
            "tp1_reward_quality": self.tp1_reward_quality,
            "target_quality": self.target_quality,
            "setup_quality": self.setup_quality,
            "execution_quality": self.execution_quality,
            "htf_alignment": self.htf_alignment,
            "timing_quality": self.timing_quality,
            "data_confidence": self.data_confidence,
            "overall_trade_quality": self.overall_trade_quality,
            "rank_score": self.rank_score,
        }


def _bounded(value: float | None) -> float | None:
    if value is None:
        return None
    return min(100.0, max(0.0, float(value)))


def _first_available(*values: float | None) -> float | None:
    for value in values:
        bounded = _bounded(value)
        if bounded is not None:
            return bounded
    return None


def _execution_precedence(setup: DiscoverySetup) -> float:
    if setup.execution_allowed_now:
        return 100.0
    if setup.confirmation_required and not setup.confirmation_complete:
        return 78.0
    if setup.entry_status in {
        EntryStatus.PULLBACK_PREFERRED,
        EntryStatus.WATCH_NEAR_ENTRY,
    }:
        return 62.0
    return 50.0


def _tp1_reward_quality(setup: DiscoverySetup) -> float:
    """Map TP1 R:R to a bounded rank input without hiding poor geometry."""

    tp1_rr = setup.take_profits[0].risk_reward
    # 1R is only middling, 2R is strong, and 3R reaches the cap.
    return round(min(100.0, max(0.0, tp1_rr / 3.0 * 100.0)), 4)


def _htf_alignment(setup: DiscoverySetup) -> float | None:
    explicit = setup.methodology_scores.directional_alignment
    if explicit is not None:
        return _bounded(explicit)

    relationship = setup.layered_state.timeframe_relationship
    severity = setup.layered_state.relationship_severity
    relationship_score = {
        TimeframeRelationship.WITH_TREND: 100.0,
        TimeframeRelationship.STRUCTURAL_REVERSAL_CONFIRMED: 90.0,
        TimeframeRelationship.MIXED: 68.0,
        TimeframeRelationship.REVERSAL_ATTEMPT: 58.0,
        TimeframeRelationship.COUNTERTREND_SCALP: 48.0,
        TimeframeRelationship.DIRECT_STRUCTURAL_OPPOSITION: 20.0,
        TimeframeRelationship.UNAVAILABLE: None,
    }[relationship]
    severity_penalty = {
        RelationshipSeverity.NONE: 0.0,
        RelationshipSeverity.MILD: 5.0,
        RelationshipSeverity.MODERATE: 12.0,
        RelationshipSeverity.STRONG: 22.0,
        RelationshipSeverity.CRITICAL: 35.0,
        RelationshipSeverity.UNAVAILABLE: 0.0,
    }[severity]
    if relationship_score is None:
        return None
    return max(0.0, relationship_score - severity_penalty)


def portfolio_rank_components(setup: DiscoverySetup) -> PortfolioRankComponents:
    """Build truthful rank inputs from already-available setup evidence."""

    quality = setup.quality_dimensions
    scores = setup.methodology_scores
    target_quality = _first_available(
        scores.reward_quality,
        quality.target_quality if quality is not None else None,
    )
    setup_quality = _first_available(
        scores.setup_quality,
        quality.setup_quality if quality is not None else None,
        setup.confidence_score,
    )
    execution_quality = _first_available(
        scores.execution_quality,
        quality.execution_quality if quality is not None else None,
    )
    timing_quality = _bounded(scores.timing_quality)
    data_confidence = _bounded(scores.data_confidence)
    overall_trade_quality = _first_available(
        scores.overall_trade_quality,
        quality.overall_trade_quality if quality is not None else None,
        setup.confidence_score,
    )
    execution_precedence = _execution_precedence(setup)
    tp1_reward_quality = _tp1_reward_quality(setup)
    htf_alignment = _htf_alignment(setup)

    weighted_components = (
        (execution_precedence, 0.22),
        (tp1_reward_quality, 0.20),
        (target_quality, 0.12),
        (setup_quality, 0.12),
        (execution_quality, 0.12),
        (htf_alignment, 0.08),
        (timing_quality, 0.05),
        (data_confidence, 0.04),
        (overall_trade_quality, 0.05),
    )
    available = tuple((value, weight) for value, weight in weighted_components if value is not None)
    available_weight = sum(weight for _, weight in available)
    rank_score = round(
        sum(value * weight for value, weight in available) / available_weight,
        4,
    )
    return PortfolioRankComponents(
        execution_precedence=execution_precedence,
        tp1_reward_quality=tp1_reward_quality,
        target_quality=target_quality,
        setup_quality=setup_quality,
        execution_quality=execution_quality,
        htf_alignment=htf_alignment,
        timing_quality=timing_quality,
        data_confidence=data_confidence,
        overall_trade_quality=overall_trade_quality,
        rank_score=rank_score,
    )


def _sortable_component(value: float | None) -> tuple[int, float]:
    if value is None:
        return (1, 0.0)
    return (0, -value)


def portfolio_ranking_key(setup: DiscoverySetup) -> tuple[object, ...]:
    """Return deterministic best-first precedence with a stable identity tie-breaker."""

    components = portfolio_rank_components(setup)
    return (
        -components.rank_score,
        -components.execution_precedence,
        -setup.take_profits[0].risk_reward,
        _sortable_component(components.target_quality),
        _sortable_component(components.setup_quality),
        _sortable_component(components.execution_quality),
        _sortable_component(components.htf_alignment),
        _sortable_component(components.data_confidence),
        # Preserve deterministic legacy winner semantics when richer dimensions
        # are equal or unavailable. Confidence remains only a late tie-breaker.
        -setup.confidence_score,
        setup.symbol,
        setup.direction.value,
        setup.strategy.value,
        setup.candidate_id,
    )


__all__ = [
    "PortfolioRankComponents",
    "portfolio_rank_components",
    "portfolio_ranking_key",
]
