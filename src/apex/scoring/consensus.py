"""Duplicate-thesis grouping and directional consensus analysis."""

from __future__ import annotations

from collections import defaultdict

from apex.scoring.config import ScoringConfig
from apex.scoring.contracts import DirectionalConsensus, RankedCandidate
from apex.strategies.contracts import TradeDirection


def _relative_difference(left: float, right: float) -> float:
    scale = max(abs(left), abs(right), 1e-12)
    return abs(left - right) / scale


def _entry_overlap(left: RankedCandidate, right: RankedCandidate) -> float:
    left_entry = left.candidate.entry
    right_entry = right.candidate.entry
    overlap = max(
        0.0, min(left_entry.upper, right_entry.upper) - max(left_entry.lower, right_entry.lower)
    )
    smaller_width = min(
        max(left_entry.upper - left_entry.lower, 1e-12),
        max(right_entry.upper - right_entry.lower, 1e-12),
    )
    return min(1.0, overlap / smaller_width)


def _shared_references(left: RankedCandidate, right: RankedCandidate) -> bool:
    left_evidence = left.candidate.evidence
    right_evidence = right.candidate.evidence
    left_refs = set(left_evidence.structure_references) | set(left_evidence.liquidity_references)
    right_refs = set(right_evidence.structure_references) | set(right_evidence.liquidity_references)
    if not left_refs or not right_refs:
        return True
    return bool(left_refs.intersection(right_refs))


def are_duplicate_theses(
    left: RankedCandidate,
    right: RankedCandidate,
    *,
    config: ScoringConfig,
) -> bool:
    """Return whether two strategies describe materially the same trade geometry."""

    if left.candidate.direction is not right.candidate.direction:
        return False
    if _entry_overlap(left, right) < config.duplicate_entry_overlap:
        return False
    if (
        _relative_difference(
            left.candidate.invalidation.price,
            right.candidate.invalidation.price,
        )
        > config.duplicate_price_tolerance
    ):
        return False
    if (
        _relative_difference(
            left.candidate.targets.levels[0].price,
            right.candidate.targets.levels[0].price,
        )
        > config.duplicate_price_tolerance
    ):
        return False
    return _shared_references(left, right)


def duplicate_groups(
    ranked: tuple[RankedCandidate, ...],
    *,
    config: ScoringConfig,
) -> tuple[tuple[str, ...], ...]:
    """Build deterministic connected groups of overlapping trade theses."""

    adjacency: dict[str, set[str]] = defaultdict(set)
    by_id = {item.scored.candidate_id: item for item in ranked}
    for index, left in enumerate(ranked):
        for right in ranked[index + 1 :]:
            if are_duplicate_theses(left, right, config=config):
                left_id = left.scored.candidate_id
                right_id = right.scored.candidate_id
                adjacency[left_id].add(right_id)
                adjacency[right_id].add(left_id)

    groups: list[tuple[str, ...]] = []
    visited: set[str] = set()
    rank_by_id = {item.scored.candidate_id: item.rank for item in ranked}
    for candidate_id in sorted(adjacency, key=rank_by_id.__getitem__):
        if candidate_id in visited:
            continue
        stack = [candidate_id]
        members: set[str] = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            members.add(current)
            stack.extend(adjacency[current].difference(visited))
        ordered = tuple(sorted(members, key=lambda value: (rank_by_id[value], value)))
        if len(ordered) > 1 and all(value in by_id for value in ordered):
            groups.append(ordered)
    return tuple(groups)


def directional_consensus(ranked: tuple[RankedCandidate, ...]) -> DirectionalConsensus:
    directions = {item.candidate.direction for item in ranked}
    if not directions:
        return DirectionalConsensus.NONE
    if directions == {TradeDirection.LONG}:
        return DirectionalConsensus.LONG
    if directions == {TradeDirection.SHORT}:
        return DirectionalConsensus.SHORT
    return DirectionalConsensus.MIXED
