"""Shared transparent score dimensions and final ranking score."""

from __future__ import annotations

from dataclasses import dataclass

from apex.scoring.contracts import ScoredCandidate


RANK_SCORE_WEIGHTS = {
    "opportunity_score": 0.25,
    "setup_score": 0.40,
    "timing_score": 0.20,
    "trade_quality_score": 0.15,
}


@dataclass(frozen=True, slots=True)
class CandidateScoreDimensions:
    """Transparent diagnostic dimensions derived