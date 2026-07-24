"""Attach canonical decision-time volatility profiles without changing authority."""

from __future__ import annotations

from dataclasses import replace

from apex.domain.decision_volatility import DecisionVolatilityProfile
from apex.strategies.actionability import classify_candidate_actionability
from apex.strategies.contracts import TradeCandidate
from apex.strategies.orchestration import CandidateActionability, StrategyAnalysisResult


def _attach(
    candidate: TradeCandidate,
    profile: DecisionVolatilityProfile,
) -> TradeCandidate:
    metadata: dict[str, str | int | float | bool] = dict(candidate.metadata)
    metadata.update(
        {key: value for key, value in profile.as_metadata().items() if value is not None}
    )
    return replace(candidate, metadata=metadata)


def attach_decision_volatility_profile(
    analysis: StrategyAnalysisResult,
    *,
    profile: DecisionVolatilityProfile,
) -> StrategyAnalysisResult:
    candidates = tuple(_attach(candidate, profile) for candidate in analysis.candidates)
    suppressed = tuple(
        replace(item, candidate=_attach(item.candidate, profile))
        for item in analysis.suppressed_candidates
    )
    actionability = tuple(
        CandidateActionability(
            candidate=candidate,
            status=classify_candidate_actionability(candidate),
        )
        for candidate in candidates
    )
    return replace(
        analysis,
        candidates=candidates,
        suppressed_candidates=suppressed,
        candidate_actionability=actionability,
    )
