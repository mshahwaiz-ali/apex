from __future__ import annotations

from types import SimpleNamespace

from apex.application.canonical_opportunity_selection import (
    select_canonical_opportunity_decision,
)
from apex.cli_commands import backtesting


def test_backtesting_uses_shared_canonical_selector() -> None:
    assert backtesting._select_replay_decision is select_canonical_opportunity_decision


def test_selector_is_independent_of_analysis_mode_metadata() -> None:
    analysis_scan = SimpleNamespace(
        opportunity_portfolio=None,
        assessment=SimpleNamespace(setup=None),
        analysis_mode="scan_cmp_first",
    )
    analysis_full = SimpleNamespace(
        opportunity_portfolio=None,
        assessment=SimpleNamespace(setup=None),
        analysis_mode="analyze_full",
    )

    scan_decision = select_canonical_opportunity_decision(analysis_scan)
    full_decision = select_canonical_opportunity_decision(analysis_full)

    assert scan_decision == full_decision
    assert scan_decision.reason_code == "legacy_no_selected_setup"


def test_selector_does_not_invent_execution_without_a_setup() -> None:
    decision = select_canonical_opportunity_decision(
        SimpleNamespace(
            opportunity_portfolio=None,
            assessment=SimpleNamespace(setup=None),
        )
    )

    assert decision.setup is None
    assert decision.execution_authorized is False
    assert decision.opportunity_id is None
