"""Typed primary and alternative candidate ranking output."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from apex.scoring import (
    CandidateOutcome,
    CandidateSelectionResult,
    RankedCandidate,
)
from apex.scoring.config import DEFAULT_SCORING_CONFIG, score_band_for
from apex.scoring.rank_score import (
    RANK_SCORE_WEIGHTS,
    CandidateScoreDimensions,
    final_rank_score,
    rank_penalty_score,
    score_dimensions,
    unpenalized_rank_score,
)
from apex.strategies import EntryStatus, classify_candidate_actionability


class CandidateRankingRole(StrEnum):
    """Role assigned after deterministic candidate ranking."""

    PRIMARY = "primary"
    ALTERNATIVE = "alternative"
    REJECTED = "rejected"


class CandidateQualityLabel(StrEnum):
    """Simple operator-facing opportunity quality label."""

    STRONG = "strong"
    USABLE = "usable"
    SPECULATIVE = "speculative"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class CandidateRankingRecord:
    """One ranked strategy candidate preserved for analysis output."""

    candidate_id: str
    rank: int
    role: CandidateRankingRole
    strategy: str
    strategy_family: str
    strategy_subtype: str | None
    direction: str
    entry_status: EntryStatus
    final_score: float
    approval_threshold: float
    score_shortfall: float
    unpenalized_rank_score: float
    rank_penalty_score: float
    final_rank_score: float
    score_band: str
    quality_label: CandidateQualityLabel
    score_dimensions: CandidateScoreDimensions
    outcome: str
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]
    entry: Mapping[str, Any]
    invalidation: Mapping[str, Any]
    targets: tuple[Mapping[str, Any], ...]
    evidence: Mapping[str, Any]
    metadata: Mapping[str, Any]
    provisional: bool

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate ranking identity cannot be empty")
        if self.rank < 1:
            raise ValueError("candidate ranking rank must be positive")
        if not 0.0 <= self.final_score <= 100.0:
            raise ValueError("candidate ranking score must be between zero and 100")
        if not 0.0 <= self.unpenalized_rank_score <= 100.0:
            raise ValueError("candidate unpenalized rank score must be between zero and 100")
        if self.rank_penalty_score < 0.0:
            raise ValueError("candidate rank penalty score cannot be negative")
        if not 0.0 <= self.final_rank_score <= 100.0:
            raise ValueError("candidate final rank score must be between zero and 100")
        if not self.score_band.strip():
            raise ValueError("candidate score band cannot be empty")
        if not self.strategy.strip() or not self.direction.strip():
            raise ValueError("candidate ranking strategy and direction cannot be empty")


@dataclass(frozen=True, slots=True)
class CandidateRankingSnapshot:
    """Selected candidate plus every preserved alternative and rejection."""

    primary: CandidateRankingRecord | None
    alternatives: tuple[CandidateRankingRecord, ...]
    rejected: tuple[CandidateRankingRecord, ...]
    ranked_count: int

    def __post_init__(self) -> None:
        records = (
            (() if self.primary is None else (self.primary,)) + self.alternatives + self.rejected
        )
        if self.ranked_count != len(records):
            raise ValueError("candidate ranking count must match preserved records")
        identities = tuple(item.candidate_id for item in records)
        if len(set(identities)) != len(identities):
            raise ValueError("candidate ranking records must have unique identities")
        if self.primary is not None and self.primary.role is not CandidateRankingRole.PRIMARY:
            raise ValueError("primary candidate must use the primary role")
        if any(item.role is not CandidateRankingRole.ALTERNATIVE for item in self.alternatives):
            raise ValueError("alternative candidates must use the alternative role")
        if any(item.role is not CandidateRankingRole.REJECTED for item in self.rejected):
            raise ValueError("rejected candidates must use the rejected role")


_VIABLE_OUTCOMES = {
    CandidateOutcome.ACCEPTED,
    CandidateOutcome.ACCEPTED_WITH_WARNING,
    CandidateOutcome.DOWNGRADED,
}


def build_candidate_ranking_snapshot(
    candidate_selection: CandidateSelectionResult,
) -> CandidateRankingSnapshot:
    """Preserve deterministic candidate rank order without changing selection."""

    selected_id = (
        candidate_selection.selected_candidate.scored.candidate_id
        if candidate_selection.selected_candidate is not None
        else None
    )
    primary: CandidateRankingRecord | None = None
    alternatives: list[CandidateRankingRecord] = []
    rejected: list[CandidateRankingRecord] = []

    for item in candidate_selection.ranked_candidates:
        if item.scored.candidate_id == selected_id:
            primary = _record(item, CandidateRankingRole.PRIMARY)
        elif item.outcome in _VIABLE_OUTCOMES:
            alternatives.append(_record(item, CandidateRankingRole.ALTERNATIVE))
        else:
            rejected.append(_record(item, CandidateRankingRole.REJECTED))

    return CandidateRankingSnapshot(
        primary=primary,
        alternatives=tuple(alternatives),
        rejected=tuple(rejected),
        ranked_count=len(candidate_selection.ranked_candidates),
    )


def candidate_ranking_payload(
    snapshot: CandidateRankingSnapshot,
) -> dict[str, object]:
    """Serialize candidate ranking with alternatives kept in rank order."""

    return {
        "primary": _record_payload(snapshot.primary) if snapshot.primary is not None else None,
        "alternatives": [_record_payload(item) for item in snapshot.alternatives],
        "rejected": [_record_payload(item) for item in snapshot.rejected],
        "ranked_count": snapshot.ranked_count,
        "alternative_count": len(snapshot.alternatives),
        "rejected_count": len(snapshot.rejected),
        "rank_score_weights": dict(RANK_SCORE_WEIGHTS),
    }


def _record(
    item: RankedCandidate,
    role: CandidateRankingRole,
) -> CandidateRankingRecord:
    alignment = item.scored.environment_route_alignment
    alignment_codes = alignment.reason_codes if alignment is not None else ()
    return CandidateRankingRecord(
        candidate_id=item.scored.candidate_id,
        rank=item.rank,
        role=role,
        strategy=item.candidate.strategy.value,
        strategy_family=item.candidate.strategy.canonical_family.value,
        strategy_subtype=item.candidate.strategy.canonical_subtype,
        direction=item.candidate.direction.value,
        entry_status=classify_candidate_actionability(item.candidate),
        final_score=item.final_score,
        approval_threshold=DEFAULT_SCORING_CONFIG.minimum_accept_score,
        score_shortfall=max(0.0, DEFAULT_SCORING_CONFIG.minimum_accept_score - item.final_score),
        unpenalized_rank_score=unpenalized_rank_score(item.scored),
        rank_penalty_score=rank_penalty_score(item.scored),
        final_rank_score=final_rank_score(item.scored),
        score_band=score_band_for(final_rank_score(item.scored)),
        quality_label=candidate_quality_label(
            final_rank_score=final_rank_score(item.scored),
            role=role,
        ),
        score_dimensions=score_dimensions(item.scored),
        outcome=item.outcome.value,
        reason_codes=tuple(dict.fromkeys((*alignment_codes,))),
        reasons=item.reasons,
        entry=_entry_payload(item.candidate),
        invalidation=_invalidation_payload(item.candidate),
        targets=_target_payloads(item.candidate),
        evidence=_evidence_payload(item.candidate),
        metadata=dict(item.candidate.metadata),
        provisional=item.candidate.provisional,
    )


def _entry_payload(candidate: Any) -> dict[str, Any]:
    entry = candidate.entry
    return {
        "lower": entry.lower,
        "upper": entry.upper,
        "preferred": entry.preferred,
        "current_price": entry.current_price,
        "maximum_chase_price": entry.max_chase_price,
        "mode": entry.mode.value,
        "distance_from_current": entry.distance_from_current,
        "atr_distance": entry.atr_distance,
        "estimated_move_missed": entry.estimated_move_missed,
        "location_quality": entry.location_quality,
        "is_extended": entry.is_extended,
        "rationale": list(entry.rationale),
    }


def _invalidation_payload(candidate: Any) -> dict[str, Any]:
    invalidation = candidate.invalidation
    return {
        "kind": invalidation.kind.value,
        "price": invalidation.price,
        "rationale": list(invalidation.rationale),
    }


def _target_payloads(candidate: Any) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "kind": level.kind.value,
            "price": level.price,
            "label": level.label,
            "rationale": list(level.rationale),
        }
        for level in candidate.targets.levels
    )


def _evidence_payload(candidate: Any) -> dict[str, Any]:
    evidence = candidate.evidence
    return {
        "supporting": list(evidence.supporting),
        "contradictions": list(evidence.contradictions),
        "warnings": list(evidence.warnings),
        "feature_references": list(evidence.feature_references),
        "structure_references": list(evidence.structure_references),
        "liquidity_references": list(evidence.liquidity_references),
    }


def candidate_quality_label(
    *,
    final_rank_score: float,
    role: CandidateRankingRole,
) -> CandidateQualityLabel:
    """Map canonical score bands and outcome role to a simple quality label."""

    if role is CandidateRankingRole.REJECTED:
        return CandidateQualityLabel.REJECTED
    band = score_band_for(final_rank_score)
    if band in {"75_84", "85_89", "90_94", "95_100"}:
        return CandidateQualityLabel.STRONG
    if band == "65_74":
        return CandidateQualityLabel.USABLE
    return CandidateQualityLabel.SPECULATIVE


def _record_payload(item: CandidateRankingRecord) -> dict[str, object]:
    return {
        "candidate_id": item.candidate_id,
        "rank": item.rank,
        "role": item.role.value,
        "strategy": item.strategy,
        "strategy_family": item.strategy_family,
        "strategy_subtype": item.strategy_subtype,
        "direction": item.direction,
        "entry_status": item.entry_status.value,
        "final_score": item.final_score,
        "approval_threshold": item.approval_threshold,
        "score_shortfall": item.score_shortfall,
        "unpenalized_rank_score": item.unpenalized_rank_score,
        "rank_penalty_score": item.rank_penalty_score,
        "final_rank_score": item.final_rank_score,
        "score_band": item.score_band,
        "quality_label": item.quality_label.value,
        "score_dimensions": {
            "opportunity_score": item.score_dimensions.opportunity_score,
            "setup_score": item.score_dimensions.setup_score,
            "timing_score": item.score_dimensions.timing_score,
            "trade_quality_score": item.score_dimensions.trade_quality_score,
        },
        "outcome": item.outcome,
        "reason_codes": list(item.reason_codes),
        "reasons": list(item.reasons),
        "entry": dict(item.entry),
        "invalidation": dict(item.invalidation),
        "targets": [dict(target) for target in item.targets],
        "evidence": dict(item.evidence),
        "metadata": dict(item.metadata),
        "provisional": item.provisional,
    }
