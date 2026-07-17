"""Deterministic candidate scoring, ranking, conflict, and selection API."""

from apex.scoring.analysis import analyze_candidate_selection
from apex.scoring.config import (
    DEFAULT_SCORING_CONFIG,
    PenaltyWeights,
    ScoringConfig,
    ScoringWeights,
    StrategyProfile,
)
from apex.scoring.contracts import (
    CandidateOutcome,
    CandidateSelectionResult,
    ConflictSummary,
    DirectionalConsensus,
    RankedCandidate,
    ScoreBreakdown,
    ScoredCandidate,
)
from apex.scoring.rank_score import (
    RANK_SCORE_WEIGHTS,
    CandidateScoreDimensions,
    final_rank_score,
    rank_penalty_score,
    score_dimensions,
    unpenalized_rank_score,
)
from apex.scoring.setup_segment import (
    SetupSegmentContext,
    SetupSegmentIdentity,
    score_band_for,
)

__all__ = [
    "DEFAULT_SCORING_CONFIG",
    "RANK_SCORE_WEIGHTS",
    "CandidateOutcome",
    "CandidateScoreDimensions",
    "CandidateSelectionResult",
    "ConflictSummary",
    "DirectionalConsensus",
    "PenaltyWeights",
    "RankedCandidate",
    "ScoreBreakdown",
    "ScoredCandidate",
    "ScoringConfig",
    "ScoringWeights",
    "SetupSegmentContext",
    "SetupSegmentIdentity",
    "StrategyProfile",
    "analyze_candidate_selection",
    "final_rank_score",
    "rank_penalty_score",
    "score_band_for",
    "score_dimensions",
    "unpenalized_rank_score",
]
