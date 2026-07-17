"""Immutable contracts for candidate scoring, ranking, and selection."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from apex.strategies.contracts import StrategyType, TradeCandidate, TradeDirection


class CandidateOutcome(StrEnum):
    ACCEPTED = "accepted"
    ACCEPTED_WITH_WARNING = "accepted_with_conflict_warning"
    DOWNGRADED = "downgraded"
    REJECTED_CONTRADICTION = "rejected_due_to_contradiction"
    REJECTED_DUPLICATE = "rejected_as_duplicate_thesis"
    REJECTED_BELOW_THRESHOLD = "rejected_below_score_threshold"


class DirectionalConsensus(StrEnum):
    LONG = "long"
    SHORT = "short"
    MIXED = "mixed"
    NONE = "none"


class EnvironmentRouteAlignmentState(StrEnum):
    ALIGNED = "aligned"
    LOWER_PRIORITY = "lower_priority"
    DIRECTION_CONFLICT = "direction_conflict"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class EnvironmentRouteAlignment:
    state: EnvironmentRouteAlignmentState
    route_priority: int | None
    preferred_direction: str
    routing_score: float
    score_adjustment: float
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.route_priority is not None and self.route_priority < 1:
            raise ValueError("environment route priority must be positive")
        _bounded_score("environment routing score", self.routing_score)
        if not math.isfinite(self.score_adjustment) or self.score_adjustment > 0.0:
            raise ValueError("environment route score adjustment must be finite and non-positive")
        if len(self.reason_codes) != len(self.reasons):
            raise ValueError("environment route reasons must match reason codes")


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _bounded_score(name: str, value: float) -> None:
    if not math.isfinite(value) or not 0.0 <= value <= 100.0:
        raise ValueError(f"{name} must be finite and between zero and 100")


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    quality_points: Mapping[str, float]
    penalty_points: Mapping[str, float]
    base_score: float
    total_penalty: float
    final_score: float

    def __post_init__(self) -> None:
        quality = dict(self.quality_points)
        penalties = dict(self.penalty_points)
        if not quality:
            raise ValueError("quality score breakdown cannot be empty")
        for name, value in (*quality.items(), *penalties.items()):
            if not name.strip() or not math.isfinite(value) or value < 0.0:
                raise ValueError("score breakdown values must be named, finite, and non-negative")
        _bounded_score("base score", self.base_score)
        if not math.isfinite(self.total_penalty) or self.total_penalty < 0.0:
            raise ValueError("total penalty must be finite and non-negative")
        _bounded_score("final score", self.final_score)
        object.__setattr__(self, "quality_points", MappingProxyType(quality))
        object.__setattr__(self, "penalty_points", MappingProxyType(penalties))


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate_id: str
    candidate: TradeCandidate
    breakdown: ScoreBreakdown
    normalized_metrics: Mapping[str, float]
    notes: tuple[str, ...] = ()
    environment_route_alignment: EnvironmentRouteAlignment | None = None

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate identity cannot be empty")
        metrics = dict(self.normalized_metrics)
        for name, value in metrics.items():
            if not name.strip() or not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError("normalized metrics must be named values in the unit interval")
        object.__setattr__(self, "normalized_metrics", MappingProxyType(metrics))

    @property
    def final_score(self) -> float:
        return self.breakdown.final_score


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    scored: ScoredCandidate
    rank: int
    outcome: CandidateOutcome
    reasons: tuple[str, ...]
    tie_break: tuple[str, ...]
    consensus_group: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError("rank must be positive")
        if self.outcome.value.startswith("rejected") and not self.reasons:
            raise ValueError("rejection reasons cannot be empty")
        if len(set(self.consensus_group)) != len(self.consensus_group):
            raise ValueError("consensus group identities must be unique")

    @property
    def candidate(self) -> TradeCandidate:
        return self.scored.candidate

    @property
    def final_score(self) -> float:
        return self.scored.final_score


@dataclass(frozen=True, slots=True)
class ConflictSummary:
    directional_consensus: DirectionalConsensus
    long_count: int
    short_count: int
    duplicate_groups: tuple[tuple[str, ...], ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.long_count < 0 or self.short_count < 0:
            raise ValueError("direction counts cannot be negative")
        for group in self.duplicate_groups:
            if len(group) < 2 or len(set(group)) != len(group):
                raise ValueError("duplicate groups must contain at least two unique identities")


@dataclass(frozen=True, slots=True)
class CandidateSelectionResult:
    symbol: str
    decision_time: datetime
    all_scored_candidates: tuple[ScoredCandidate, ...]
    ranked_candidates: tuple[RankedCandidate, ...]
    rejected_candidates: tuple[RankedCandidate, ...]
    conflict_summary: ConflictSummary
    directional_consensus: DirectionalConsensus
    selected_candidate: RankedCandidate | None
    no_trade_reason: str | None
    evaluated_strategy_order: tuple[StrategyType, ...]
    configuration_id: str
    metadata: Mapping[str, str | int | float | bool]

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("result symbol cannot be empty")
        _aware("result decision time", self.decision_time)
        if not self.configuration_id.strip():
            raise ValueError("configuration identifier cannot be empty")
        if len(set(self.evaluated_strategy_order)) != len(self.evaluated_strategy_order):
            raise ValueError("evaluated strategy order must contain unique strategies")

        identities = tuple(item.candidate_id for item in self.all_scored_candidates)
        if len(set(identities)) != len(identities):
            raise ValueError("candidate identities must be unique")
        ranks = tuple(item.rank for item in self.ranked_candidates)
        if ranks != tuple(range(1, len(ranks) + 1)):
            raise ValueError("ranked candidates must have contiguous ranks")
        ranked_ids = {item.scored.candidate_id for item in self.ranked_candidates}
        rejected_ids = {item.scored.candidate_id for item in self.rejected_candidates}
        if not rejected_ids.issubset(ranked_ids):
            raise ValueError("rejected candidates must belong to ranked candidates")
        if self.selected_candidate is not None:
            selected_id = self.selected_candidate.scored.candidate_id
            if selected_id not in ranked_ids:
                raise ValueError("selected candidate must belong to ranked candidates")
            if self.no_trade_reason is not None:
                raise ValueError("selected trade cannot also have a no-trade reason")
        elif not self.no_trade_reason or not self.no_trade_reason.strip():
            raise ValueError("no-trade result requires a reason")
        if self.directional_consensus is not self.conflict_summary.directional_consensus:
            raise ValueError("directional consensus must match conflict summary")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def selected_direction(self) -> TradeDirection | None:
        if self.selected_candidate is None:
            return None
        return self.selected_candidate.candidate.direction
