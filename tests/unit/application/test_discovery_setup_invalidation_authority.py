from types import SimpleNamespace

from apex.application import discovery_setup
from apex.scoring.contracts import CandidateOutcome
from apex.strategies.entry_status import EntryStatus


def test_invalidated_candidate_is_never_public_even_when_scoring_accepted(
    monkeypatch,
) -> None:
    candidate = SimpleNamespace()
    ranked = SimpleNamespace(
        candidate=candidate,
        outcome=CandidateOutcome.ACCEPTED,
    )
    monkeypatch.setattr(
        discovery_setup,
        "classify_candidate_actionability",
        lambda _candidate: EntryStatus.INVALIDATED,
    )

    assert not discovery_setup._is_public_setup_candidate(ranked)
