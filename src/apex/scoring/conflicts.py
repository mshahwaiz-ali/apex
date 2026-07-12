"""Explicit conflict resolution for ranked Phase 5 candidates."""

from __future__ import annotations

from dataclasses import replace

from apex.scoring.config import ScoringConfig
from apex.scoring.consensus import directional_consensus, duplicate_groups
from apex.scoring.contracts import (
    CandidateOutcome,
    ConflictSummary,
    DirectionalConsensus,
    RankedCandidate,
)
from apex.strategies.contracts import TradeDirection


def _group_lookup(groups: tuple[tuple[str, ...], ...]) -> dict[str, tuple[str, ...]]:
    return {candidate_id: group for group in groups for candidate_id in group}


def _direction_counts(ranked: tuple[RankedCandidate, ...]) -> tuple[int, int]:
    long_count = sum(item.candidate.direction is TradeDirection.LONG for item in ranked)
    short_count = sum(item.candidate.direction is TradeDirection.SHORT for item in ranked)
    return long_count, short_count


def resolve_conflicts(
    ranked: tuple[RankedCandidate, ...],
    *,
    config: ScoringConfig,
) -> tuple[tuple[RankedCandidate, ...], ConflictSummary]:
    """Assign explicit outcomes without changing deterministic rank order."""

    groups = duplicate_groups(ranked, config=config)
    group_by_id = _group_lookup(groups)
    consensus = directional_consensus(ranked)
    long_count, short_count = _direction_counts(ranked)
    warnings: list[str] = []

    best_long = next(
        (item for item in ranked if item.candidate.direction is TradeDirection.LONG),
        None,
    )
    best_short = next(
        (item for item in ranked if item.candidate.direction is TradeDirection.SHORT),
        None,
    )
    unresolved_directional_conflict = (
        best_long is not None
        and best_short is not None
        and abs(best_long.final_score - best_short.final_score)
        <= config.unresolved_conflict_margin
    )
    if unresolved_directional_conflict:
        warnings.append("opposing directions remain within the unresolved conflict margin")

    resolved: list[RankedCandidate] = []
    for item in ranked:
        candidate_id = item.scored.candidate_id
        group = group_by_id.get(candidate_id, ())
        reasons: list[str] = []
        outcome = CandidateOutcome.DOWNGRADED

        if group and candidate_id != group[0]:
            outcome = CandidateOutcome.REJECTED_DUPLICATE
            reasons.append(f"duplicate thesis supports primary candidate {group[0]}")
        elif item.final_score < config.warning_accept_score:
            outcome = CandidateOutcome.REJECTED_BELOW_THRESHOLD
            reasons.append(
                f"score {item.final_score:.2f} is below aggressive floor "
                f"{config.warning_accept_score:.2f}"
            )
        elif (
            item.scored.breakdown.penalty_points.get(
                "higher_timeframe_contradiction", 0.0
            )
            >= config.penalties.higher_timeframe_contradiction
        ):
            outcome = CandidateOutcome.REJECTED_CONTRADICTION
            reasons.append("major higher-timeframe contradiction invalidates selection")
        elif unresolved_directional_conflict:
            direction_leader = (
                best_long
                if item.candidate.direction is TradeDirection.LONG
                else best_short
            )
            if direction_leader is item:
                outcome = CandidateOutcome.DOWNGRADED
                reasons.append("equal-strength opposing direction prevents final acceptance")
            else:
                outcome = CandidateOutcome.REJECTED_CONTRADICTION
                reasons.append("opposing direction leader outranks this conflicting candidate")
        elif item.final_score >= config.minimum_accept_score:
            if item.candidate.provisional or consensus is DirectionalConsensus.MIXED:
                outcome = CandidateOutcome.ACCEPTED_WITH_WARNING
                if item.candidate.provisional:
                    reasons.append("qualified provisional evidence accepted with penalty")
                if consensus is DirectionalConsensus.MIXED:
                    reasons.append("opposing directional evidence remains below winner strength")
            else:
                outcome = CandidateOutcome.ACCEPTED
                reasons.append("candidate clears score and conflict requirements")
        else:
            outcome = CandidateOutcome.ACCEPTED_WITH_WARNING
            reasons.append("aggressive candidate accepted inside warning threshold band")

        resolved.append(
            replace(
                item,
                outcome=outcome,
                reasons=tuple(reasons),
                consensus_group=group,
            )
        )

    return (
        tuple(resolved),
        ConflictSummary(
            directional_consensus=consensus,
            long_count=long_count,
            short_count=short_count,
            duplicate_groups=groups,
            warnings=tuple(warnings),
        ),
    )
