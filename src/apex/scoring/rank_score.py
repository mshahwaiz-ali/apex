"""Shared transparent score dimensions and final ranking score."""

from __future__ import annotations

from dataclasses import dataclass

from apex.scoring.contracts import ScoredCandidate


RANK_SCORE_WEIGHTS = {
    "opportunity_score": 0.30,
    "setup_score": 0.35,
    "timing_score": 0.20,
    "risk_feasibility_score": 0.15,
}


@dataclass(frozen=True, slots=True)
class CandidateScoreDimensions:
    """Transparent diagnostic dimensions derived from existing quality metrics."""

    opportunity_score: float
    setup_score: float
    timing_score: float
    risk_feasibility_score: float

    def __post_init__(self) -> None:
        for name in (
            "opportunity_score",
            "setup_score",
            "timing_score",
            "risk_feasibility_score",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{name.replace('_', ' ')} must be between zero and 100")


def score_dimensions(item: ScoredCandidate) -> CandidateScoreDimensions:
    """Group existing normalized metrics into the four redesign dimensions."""

    metrics = item.normalized_metrics
    return CandidateScoreDimensions(
        opportunity_score=_percentage_mean(
            metrics["momentum_quality"],
            metrics["volume_quality"],
            metrics["liquidity_quality"],
        ),
        setup_score=_percentage_mean(
            metrics["trend_alignment"],
            metrics["structure_quality"],
        ),
        timing_score=round(metrics["entry_quality"] * 100.0, 6),
        risk_feasibility_score=round(metrics["target_space_quality"] * 100.0, 6),
    )


def final_rank_score(item: ScoredCandidate) -> float:
    """Return the opportunity/setup-heavy deterministic ranking score."""

    dimensions = score_dimensions(item)
    return round(
        dimensions.opportunity_score * RANK_SCORE_WEIGHTS["opportunity_score"]
        + dimensions.setup_score * RANK_SCORE_WEIGHTS["setup_score"]
        + dimensions.timing_score * RANK_SCORE_WEIGHTS["timing_score"]
        + dimensions.risk_feasibility_score
        * RANK_SCORE_WEIGHTS["risk_feasibility_score"],
        6,
    )


def _percentage_mean(*values: float) -> float:
    return round(sum(values) / len(values) * 100.0, 6)
