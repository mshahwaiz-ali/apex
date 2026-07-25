from __future__ import annotations

from types import SimpleNamespace

from apex.application import canonical_opportunity_selection as module
from apex.application.discovery_contracts import DiscoverySetup
from apex.application.opportunity_portfolio import ActionabilityState, SequenceRole


def _setup(candidate_id: str, *, conditional: bool, executable: bool) -> DiscoverySetup:
    setup = object.__new__(DiscoverySetup)
    object.__setattr__(setup, "candidate_id", candidate_id)
    object.__setattr__(setup, "conditional_plan", object() if conditional else None)
    object.__setattr__(setup, "execution_allowed_now", executable)
    return setup


def test_replay_selector_returns_every_distinct_replayable_opportunity(monkeypatch) -> None:
    executable = _setup("current", conditional=False, executable=True)
    conditional = _setup("nearby", conditional=True, executable=False)
    ignored = _setup("ignored", conditional=False, executable=False)

    opportunities = (
        SimpleNamespace(
            setup=executable,
            sequence_role=SequenceRole.CURRENT,
            opportunity_id="current",
            effective_lane=None,
        ),
        SimpleNamespace(
            setup=conditional,
            sequence_role=SequenceRole.NEARBY,
            opportunity_id="nearby",
            effective_lane=None,
        ),
        SimpleNamespace(
            setup=ignored,
            sequence_role=SequenceRole.FOLLOW_UP,
            opportunity_id="ignored",
            effective_lane=None,
        ),
    )
    analysis = SimpleNamespace(opportunity_portfolio=SimpleNamespace(opportunities=opportunities))

    def assess(setup: DiscoverySetup, *, sequence_role: SequenceRole):
        state = (
            ActionabilityState.EXECUTE_NOW
            if setup is executable
            else ActionabilityState.RETEST_PREFERRED
        )
        return SimpleNamespace(state=state, has_blocking_issue=False)

    monkeypatch.setattr(module, "build_actionability_state_assessment", assess)

    decisions = module.select_replay_opportunity_decisions(analysis)

    assert [item.opportunity_id for item in decisions] == ["current", "nearby"]
    assert [item.execution_authorized for item in decisions] == [True, False]


def test_replay_selector_deduplicates_opportunity_ids(monkeypatch) -> None:
    setup = _setup("candidate", conditional=True, executable=False)
    opportunity = SimpleNamespace(
        setup=setup,
        sequence_role=SequenceRole.NEARBY,
        opportunity_id="same",
        effective_lane=None,
    )
    analysis = SimpleNamespace(
        opportunity_portfolio=SimpleNamespace(opportunities=(opportunity, opportunity))
    )
    monkeypatch.setattr(
        module,
        "build_actionability_state_assessment",
        lambda setup, *, sequence_role: SimpleNamespace(
            state=ActionabilityState.RETEST_PREFERRED,
            has_blocking_issue=False,
        ),
    )

    decisions = module.select_replay_opportunity_decisions(analysis)

    assert len(decisions) == 1


def test_replay_selector_does_not_let_unreplayable_duplicate_hide_valid_setup(
    monkeypatch,
) -> None:
    invalid = _setup("invalid", conditional=False, executable=False)
    conditional = _setup("conditional", conditional=True, executable=False)
    opportunities = (
        SimpleNamespace(
            setup=invalid,
            sequence_role=SequenceRole.NEARBY,
            opportunity_id="same",
            effective_lane=None,
        ),
        SimpleNamespace(
            setup=conditional,
            sequence_role=SequenceRole.NEARBY,
            opportunity_id="same",
            effective_lane=None,
        ),
    )
    analysis = SimpleNamespace(opportunity_portfolio=SimpleNamespace(opportunities=opportunities))

    def assess(setup: DiscoverySetup, *, sequence_role: SequenceRole):
        state = (
            ActionabilityState.INVALIDATED
            if setup is invalid
            else ActionabilityState.RETEST_PREFERRED
        )
        return SimpleNamespace(state=state, has_blocking_issue=False)

    monkeypatch.setattr(module, "build_actionability_state_assessment", assess)

    decisions = module.select_replay_opportunity_decisions(analysis)

    assert len(decisions) == 1
    assert decisions[0].setup is conditional
    assert decisions[0].opportunity_id == "same"
    assert decisions[0].reason_code == "diagnostic_conditional_opportunity"


def test_canonical_selector_does_not_invent_pending_setup_without_conditional_plan(
    monkeypatch,
) -> None:
    setup = _setup("watch-only", conditional=False, executable=False)
    opportunity = SimpleNamespace(
        setup=setup,
        sequence_role=SequenceRole.NEARBY,
        opportunity_id="watch-only",
        effective_lane=None,
    )
    analysis = SimpleNamespace(
        opportunity_portfolio=SimpleNamespace(opportunities=(opportunity,))
    )
    monkeypatch.setattr(
        module,
        "build_actionability_state_assessment",
        lambda setup, *, sequence_role: SimpleNamespace(
            state=ActionabilityState.RETEST_PREFERRED,
            has_blocking_issue=False,
        ),
    )

    decision = module.select_canonical_opportunity_decision(analysis)

    assert decision.setup is None
    assert decision.opportunity_id is None
    assert decision.reason_code == "canonical_no_executable_opportunity"
    assert decision.execution_authorized is False


def test_blocking_issue_excludes_conditional_setup_from_all_replay_authority(
    monkeypatch,
) -> None:
    setup = _setup("blocked-conditional", conditional=True, executable=False)
    opportunity = SimpleNamespace(
        setup=setup,
        sequence_role=SequenceRole.NEARBY,
        opportunity_id="blocked-conditional",
        effective_lane=None,
    )
    analysis = SimpleNamespace(
        opportunity_portfolio=SimpleNamespace(opportunities=(opportunity,))
    )
    monkeypatch.setattr(
        module,
        "build_actionability_state_assessment",
        lambda setup, *, sequence_role: SimpleNamespace(
            state=ActionabilityState.RETEST_PREFERRED,
            has_blocking_issue=True,
        ),
    )

    canonical = module.select_canonical_opportunity_decision(analysis)
    diagnostic = module.select_replay_opportunity_decisions(analysis)

    assert canonical.setup is None
    assert canonical.reason_code == "canonical_no_executable_opportunity"
    assert canonical.execution_authorized is False
    assert diagnostic == ()


def test_legacy_replay_excludes_unreplayable_selected_setup(monkeypatch) -> None:
    setup = _setup("legacy-watch", conditional=False, executable=False)
    analysis = SimpleNamespace(
        opportunity_portfolio=None,
        assessment=SimpleNamespace(setup=setup),
    )
    monkeypatch.setattr(
        module,
        "build_actionability_state_assessment",
        lambda setup, *, sequence_role: SimpleNamespace(
            state=ActionabilityState.RETEST_PREFERRED,
            has_blocking_issue=False,
        ),
    )

    decisions = module.select_replay_opportunity_decisions(analysis)

    assert decisions == ()


def test_legacy_replay_preserves_valid_conditional_selected_setup(monkeypatch) -> None:
    setup = _setup("legacy-conditional", conditional=True, executable=False)
    analysis = SimpleNamespace(
        opportunity_portfolio=None,
        assessment=SimpleNamespace(setup=setup),
    )
    monkeypatch.setattr(
        module,
        "build_actionability_state_assessment",
        lambda setup, *, sequence_role: SimpleNamespace(
            state=ActionabilityState.RETEST_PREFERRED,
            has_blocking_issue=False,
        ),
    )

    decisions = module.select_replay_opportunity_decisions(analysis)

    assert len(decisions) == 1
    assert decisions[0].setup is setup
    assert decisions[0].reason_code == "legacy_selected_setup"
    assert decisions[0].execution_authorized is False
