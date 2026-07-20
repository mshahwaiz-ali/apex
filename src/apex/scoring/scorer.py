"""Transparent deterministic candidate scoring."""

from __future__ import annotations

from apex.scoring.config import QUALITY_COMPONENTS, ScoringConfig
from apex.scoring.contracts import ScoreBreakdown, ScoredCandidate
from apex.strategies.candidate_identity import candidate_identity
from apex.strategies.contracts import TradeCandidate


def _higher_timeframe_contradiction(candidate: TradeCandidate) -> float:
    metadata_value = candidate.metadata.get("higher_timeframe_contradiction", 0.0)
    if isinstance(metadata_value, bool):
        return 1.0 if metadata_value else 0.0
    if isinstance(metadata_value, (int, float)):
        return min(1.0, max(0.0, float(metadata_value)))
    return 0.0


def _normalized_metrics(candidate: TradeCandidate, config: ScoringConfig) -> dict[str, float]:
    profile = config.strategy_profiles[candidate.strategy]
    metrics: dict[str, float] = {}
    for name in QUALITY_COMPONENTS:
        raw_value = float(getattr(candidate.quality, name))
        metrics[name] = profile.neutral_value if name in profile.neutral_metrics else raw_value
    return metrics


def score_candidate(
    candidate: TradeCandidate,
    *,
    occurrence: int,
    config: ScoringConfig,
) -> ScoredCandidate:
    """Score one raw strategy candidate without mutating it."""

    metrics = _normalized_metrics(candidate, config)
    quality_points = {
        name: metrics[name] * config.weights.as_mapping()[name] * 100.0
        for name in QUALITY_COMPONENTS
    }
    base_score = sum(quality_points.values())

    contradiction = _higher_timeframe_contradiction(candidate)
    penalty_inputs = {
        "extension_penalty": candidate.quality.extension_penalty,
        "conflict_penalty": candidate.quality.conflict_penalty,
        "provisional_penalty": 1.0 if candidate.provisional else 0.0,
        "higher_timeframe_contradiction": contradiction,
    }
    penalty_points = {
        name: value * config.penalties.as_mapping()[name] for name, value in penalty_inputs.items()
    }
    total_penalty = sum(penalty_points.values())
    final_score = min(100.0, max(0.0, base_score - total_penalty))

    notes: list[str] = []
    profile = config.strategy_profiles[candidate.strategy]
    for name in sorted(profile.neutral_metrics):
        notes.append(f"{name} normalized to explicit neutral value {profile.neutral_value:.2f}")
    if candidate.provisional:
        notes.append("provisional evidence retained with explicit penalty")
    if contradiction > 0.0:
        notes.append("higher-timeframe contradiction penalty applied")

    return ScoredCandidate(
        candidate_id=candidate_identity(candidate, occurrence),
        candidate=candidate,
        breakdown=ScoreBreakdown(
            quality_points=quality_points,
            penalty_points=penalty_points,
            base_score=base_score,
            total_penalty=total_penalty,
            final_score=final_score,
        ),
        normalized_metrics=metrics,
        notes=tuple(notes),
    )


def score_candidates(
    candidates: tuple[TradeCandidate, ...],
    *,
    config: ScoringConfig,
) -> tuple[ScoredCandidate, ...]:
    """Score candidates in stable input order with deterministic identities."""

    occurrences: dict[tuple[str, str], int] = {}
    scored: list[ScoredCandidate] = []
    for candidate in candidates:
        key = (candidate.strategy.value, candidate.direction.value)
        occurrence = occurrences.get(key, 0)
        occurrences[key] = occurrence + 1
        scored.append(score_candidate(candidate, occurrence=occurrence, config=config))
    return tuple(scored)
