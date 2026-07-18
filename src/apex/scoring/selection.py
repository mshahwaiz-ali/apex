"""Final deterministic trade selection."""

from __future__ import annotations

from apex.scoring.config import ScoringConfig
from apex.scoring.contracts import CandidateOutcome, RankedCandidate
from apex.strategies import classify_candidate_actionability
from apex.strategies.entry_status import EntryStatus

_SELECTABLE = {
    CandidateOutcome.ACCEPTED,
    CandidateOutcome.ACCEPTED_WITH_WARNING,
}
_EXECUTABLE_ENTRY_STATUSES = {
    EntryStatus.READY_NOW,
    EntryStatus.AGGRESSIVE_NOW,
}


def is_entry_status_executable(status: EntryStatus) -> bool:
    """Return whether an entry state authorizes current execution."""

    return status in _EXECUTABLE_ENTRY_STATUSES


def _selection_score(item: RankedCandidate, config: ScoringConfig) -> float:
    supporters = max(0, len(item.consensus_group) - 1)
    bonus = min(
        config.maximum_consensus_bonus,
        supporters * config.consensus_bonus_per_supporter,
    )
    return item.final_score + bonus


def select_candidate(
    ranked: tuple[RankedCandidate, ...],
    *,
    config: ScoringConfig,
) -> RankedCandidate | None:
    """Select one accepted candidate, allowing bounded consensus support."""

    selectable = tuple(
        item
        for item in ranked
        if item.outcome in _SELECTABLE
        and is_entry_status_executable(classify_candidate_actionability(item.candidate))
    )
    if not selectable:
        return None
    return min(
        selectable,
        key=lambda item: (
            -_selection_score(item, config),
            item.rank,
            item.scored.candidate_id,
        ),
    )


def no_trade_reason(ranked: tuple[RankedCandidate, ...]) -> str:
    """Return an explicit deterministic reason when nothing is selectable."""

    if not ranked:
        return "no strategy candidates were generated"
    outcomes = {item.outcome for item in ranked}
    accepted = tuple(item for item in ranked if item.outcome in _SELECTABLE)
    if accepted and not any(
        is_entry_status_executable(classify_candidate_actionability(item.candidate))
        for item in accepted
    ):
        return "valid setups exist, but none has a currently executable entry"
    if outcomes == {CandidateOutcome.REJECTED_BELOW_THRESHOLD}:
        return "all candidates scored below their configured approval thresholds"
    if CandidateOutcome.DOWNGRADED in outcomes:
        return "opposing candidates remain unresolved inside the conflict margin"
    if CandidateOutcome.REJECTED_CONTRADICTION in outcomes:
        return "all leading candidates were invalidated by major contradiction"
    return "all candidates were rejected by deterministic candidate-selection rules"
