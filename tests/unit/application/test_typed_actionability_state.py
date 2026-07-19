from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    TakeProfit,
)
from apex.application.opportunity_portfolio import (
    ActionabilityClassificationBasis,
    ActionabilityState,
    AnalysisMode,
    SequenceRole,
    build_actionability_state_assessment,
    opportunity_portfolio_payload,
    portfolio_from_setups,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _setup(
    candidate_id: str,
    *,
    cmp: float = 100.0,
    executable: bool,
    entry_status: EntryStatus,
) -> DiscoverySetup:
    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=entry_status,
        decision_time=NOW,
        candidate_id=candidate_id,
        confidence_score=70.0,
        entry=ActionableEntry(99.0, 101.0, 100.0, cmp, 102.0, 99.0 <= cmp <= 101.0),
        stop_loss=StopLoss(97.0, 3.0, 3.0, ("structure",)),
        take_profits=(TakeProfit("TP1", 106.0, 6.0, 2.0, ("liquidity",)),),
        management_policies=(
            ManagementPolicy(
                ManagementPolicyType.TIME_EXIT,
                "expiry",
                "cancel",
                ("stale",),
            ),
        ),
        execution_allowed_now=executable,
    )


@pytest.mark.parametrize(
    ("entry_status", "expected"),
    (
        (EntryStatus.READY_NOW, ActionabilityState.EXECUTE_NOW),
        (EntryStatus.AGGRESSIVE_NOW, ActionabilityState.AGGRESSIVE_NOW),
    ),
)
def test_inside_zone_immediate_states(
    entry_status: EntryStatus,
    expected: ActionabilityState,
) -> None:
    setup = _setup(entry_status.value, executable=True, entry_status=entry_status)
    result = build_actionability_state_assessment(
        setup,
        sequence_role=SequenceRole.CURRENT,
    )
    assert result.state is expected
    assert result.basis is ActionabilityClassificationBasis.EXECUTABLE_INSIDE_ZONE
    assert result.is_legacy_projection is True


def test_poor_location_does_not_change_execution_or_role() -> None:
    setup = _setup("poor", cmp=98.0, executable=True, entry_status=EntryStatus.READY_NOW)
    result = build_actionability_state_assessment(
        setup,
        sequence_role=SequenceRole.CURRENT,
    )
    assert result.state is ActionabilityState.CMP_AVAILABLE_BUT_POOR_LOCATION
    assert result.execution_allowed_now is True
    assert result.sequence_role is SequenceRole.CURRENT


def test_chase_and_invalidation_precedence() -> None:
    chased = _setup("chased", cmp=103.0, executable=True, entry_status=EntryStatus.READY_NOW)
    invalid = _setup(
        "invalid",
        cmp=103.0,
        executable=True,
        entry_status=EntryStatus.INVALIDATED,
    )
    assert (
        build_actionability_state_assessment(
            chased,
            sequence_role=SequenceRole.CURRENT,
        ).state
        is ActionabilityState.MISSED_OR_CHASING
    )
    assert (
        build_actionability_state_assessment(
            invalid,
            sequence_role=SequenceRole.CURRENT,
        ).state
        is ActionabilityState.INVALIDATED
    )


def test_pullback_and_watch_map_conservatively() -> None:
    pullback = _setup(
        "pullback",
        executable=False,
        entry_status=EntryStatus.PULLBACK_PREFERRED,
    )
    watch = _setup("watch", executable=False, entry_status=EntryStatus.WATCH_NEAR_ENTRY)
    assert (
        build_actionability_state_assessment(
            pullback,
            sequence_role=SequenceRole.NEARBY,
        ).state
        is ActionabilityState.RETEST_PREFERRED
    )
    assert (
        build_actionability_state_assessment(
            watch,
            sequence_role=SequenceRole.NEARBY,
        ).state
        is ActionabilityState.DEVELOPING
    )


def test_serialization_is_additive_and_preserves_legacy_fields() -> None:
    setup = _setup(
        "serialized",
        executable=True,
        entry_status=EntryStatus.AGGRESSIVE_NOW,
    )
    portfolio = portfolio_from_setups(
        (setup,),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )
    payload = opportunity_portfolio_payload(portfolio)["current_long"]
    assert payload is not None
    assert payload["actionability_state"] == {
        "state": "aggressive_now",
        "basis": "executable_inside_zone",
        "source_entry_status": "AGGRESSIVE_NOW",
        "execution_allowed_now": True,
        "location_state": "inside_entry_zone",
        "sequence_role": "current",
        "issues": [],
        "has_blocking_issue": False,
        "is_legacy_projection": True,
    }
    assert payload["entry_status"] == "AGGRESSIVE_NOW"
    assert payload["execution_allowed_now"] is True


def test_scan_analyze_state_parity() -> None:
    setup = _setup(
        "parity",
        executable=False,
        entry_status=EntryStatus.PULLBACK_PREFERRED,
    )
    scan = portfolio_from_setups(
        (setup,),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )
    analyze = portfolio_from_setups(
        (replace(setup),),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )
    scan_payload = opportunity_portfolio_payload(scan)["nearby_long"]
    analyze_payload = opportunity_portfolio_payload(analyze)["nearby_long"]
    assert scan_payload is not None
    assert analyze_payload is not None
    assert scan_payload["actionability_state"] == analyze_payload["actionability_state"]
