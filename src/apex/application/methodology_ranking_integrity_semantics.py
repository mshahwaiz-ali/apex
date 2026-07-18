"""Interpret candidate ranking without allowing rank or score to authorize execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.discovery_contracts import SymbolAnalysis
from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class RankingIntegritySemantics:
    """Public interpretation of relative candidate rank versus execution validity."""

    ranking_available: bool
    ranked_count: int
    primary_available: bool
    primary_rank: int | None
    primary_score: float | None
    primary_quality_label: str | None
    primary_outcome: str | None
    alternative_count: int
    rejected_count: int
    methodology_executable: bool
    hard_blocker_count: int
    rank_authorizes_execution: bool
    interpretation: str
    limitations: tuple[str, ...]


def derive_ranking_integrity_semantics(
    analysis: SymbolAnalysis,
    methodology: MethodologySnapshot,
) -> RankingIntegritySemantics:
    """Describe ranking as relative ordering while preserving methodology gates."""

    ranking = analysis.candidate_ranking
    primary = None if ranking is None else ranking.primary
    ranked_count = 0 if ranking is None else ranking.ranked_count
    alternatives = 0 if ranking is None else len(ranking.alternatives)
    rejected = 0 if ranking is None else len(ranking.rejected)
    blocker_count = len(methodology.hard_blockers)

    if ranking is None:
        interpretation = "candidate ranking is unavailable; relative opportunity order must not be inferred"
    elif primary is None:
        interpretation = "candidates were ranked, but no primary candidate was selected"
    elif blocker_count:
        interpretation = (
            "a primary ranked candidate exists, but methodology hard blockers prevent execution"
        )
    elif not methodology.executable:
        interpretation = (
            "a primary ranked candidate exists, but canonical execution geometry is incomplete"
        )
    else:
        interpretation = (
            "the primary candidate is both top-ranked and methodology-executable; rank remains "
            "relative ordering rather than independent authorization"
        )

    return RankingIntegritySemantics(
        ranking_available=ranking is not None,
        ranked_count=ranked_count,
        primary_available=primary is not None,
        primary_rank=None if primary is None else primary.rank,
        primary_score=None if primary is None else primary.final_rank_score,
        primary_quality_label=None if primary is None else primary.quality_label.value,
        primary_outcome=None if primary is None else primary.outcome,
        alternative_count=alternatives,
        rejected_count=rejected,
        methodology_executable=methodology.executable,
        hard_blocker_count=blocker_count,
        rank_authorizes_execution=False,
        interpretation=interpretation,
        limitations=(
            "rank is relative ordering among evaluated candidates, not win probability",
            "quality labels describe ranked opportunity quality, not execution permission",
            "hard blockers and incomplete geometry take precedence over every rank score",
            "a rejected candidate cannot be repaired by ranking above another rejected candidate",
        ),
    )


def ranking_integrity_semantics_payload(
    semantics: RankingIntegritySemantics,
) -> dict[str, Any]:
    """Serialize ranking-integrity interpretation."""

    return {
        "ranking_available": semantics.ranking_available,
        "ranked_count": semantics.ranked_count,
        "primary_available": semantics.primary_available,
        "primary_rank": semantics.primary_rank,
        "primary_score": semantics.primary_score,
        "primary_quality_label": semantics.primary_quality_label,
        "primary_outcome": semantics.primary_outcome,
        "alternative_count": semantics.alternative_count,
        "rejected_count": semantics.rejected_count,
        "methodology_executable": semantics.methodology_executable,
        "hard_blocker_count": semantics.hard_blocker_count,
        "rank_authorizes_execution": semantics.rank_authorizes_execution,
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


__all__ = [
    "RankingIntegritySemantics",
    "derive_ranking_integrity_semantics",
    "ranking_integrity_semantics_payload",
]
