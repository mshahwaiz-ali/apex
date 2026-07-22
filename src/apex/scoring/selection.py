"""Final deterministic trade selection."""

from __future__ import annotations

from dataclasses import replace

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
    """Select the best candidate that authorizes execution at decision time."""

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


def _selection_precedence(item: RankedCandidate) -> int:
    """Order executable, future-trigger, and valid re-entry setups."""

    status = classify_candidate_actionability(item.candidate)
    if is_entry_status_executable(status):
        return 0
    if status not in {EntryStatus.INVALIDATED, EntryStatus.MISSED_ENTRY}:
        return 1
    if status is EntryStatus.MISSED_ENTRY and _has_valid_reentry(item):
        return 2
    return 3


def _has_valid_reentry(item: RankedCandidate) -> bool:
    """Return whether a missed primary entry still has a usable future opportunity."""

    candidate = item.candidate
    for opportunity in candidate.entry_opportunities[1:]:
        alternate = replace(candidate, entry=opportunity)
        status = classify_candidate_actionability(alternate)
        if status not in {EntryStatus.INVALIDATED, EntryStatus.MISSED_ENTRY}:
            return True
    return False


def select_future_candidate(
    ranked: tuple[RankedCandidate, ...],
    *,
    config: ScoringConfig,
) -> RankedCandidate | None:
    """Select the best accepted setup whose valid entry is still pending."""

    selectable = tuple(
        item
        for item in ranked
        if item.outcome in _SELECTABLE and _selection_precedence(item) in {1, 2}
    )
    if not selectable:
        return None
    return min(
        selectable,
        key=lambda item: (
            _selection_precedence(item),
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
    if accepted and not any(_selection_precedence(item) < 3 for item in accepted):
        return "no accepted candidate retains valid current or future entry geometry"
    if outcomes == {CandidateOutcome.REJECTED_BELOW_THRESHOLD}:
        return "all candidates scored below their configured approval thresholds"
    if CandidateOutcome.DOWNGRADED in outcomes:
        return "opposing candidates remain unresolved inside the conflict margin"
    if CandidateOutcome.REJECTED_CONTRADICTION in outcomes:
        return "all leading candidates were invalidated by major contradiction"
    return "all candidates were rejected by deterministic candidate-selection rules"
