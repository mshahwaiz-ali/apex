from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    TakeProfit,
)
from apex.application.opportunity_portfolio import (
    AnalysisMode,
    CmpActionabilityState,
    SequenceRole,
    build_cmp_actionability_diagnostics,
    classify_setup_sequence_role,
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
    lower: float = 99.0,
    upper: float = 101.0,
    maximum_chase: float = 102.0,
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
        entry=ActionableEntry(
            lower,
            upper,
            100.0,
            cmp,
            maximum_chase,
            lower <= cmp <= upper,
        ),
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


def test_executable_inside_zone_is_reported_without_changing_sequence_role() -> None:
    setup = _setup("current", executable=True, entry_status=EntryStatus.READY_NOW)

    diagnostics = build_cmp_actionability_diagnostics(setup)

    assert diagnostics.state is CmpActionabilityState.EXECUTABLE_AT_CMP
    assert classify_setup_sequence_role(setup) is SequenceRole.CURRENT


def test_execution_authorized_outside_zone_reports_conflict_without_demotion() -> None:
    setup = _setup(
        "conflict",
        cmp=98.0,
        executable=True,
        entry_status=EntryStatus.READY_NOW,
    )

    diagnostics = build_cmp_actionability_diagnostics(setup)

    assert diagnostics.state is CmpActionabilityState.EXECUTION_GEOMETRY_CONFLICT
    assert diagnostics.execution_allowed_now is True
    assert classify_setup_sequence_role(setup) is SequenceRole.CURRENT


def test_non_executable_setup_remains_nearby_even_when_cmp_is_inside_zone() -> None:
    setup = _setup(
        "nearby",
        executable=False,
        entry_status=EntryStatus.PULLBACK_PREFERRED,
    )

    diagnostics = build_cmp_actionability_diagnostics(setup)

    assert diagnostics.state is CmpActionabilityState.NEARBY_SETUP
    assert classify_setup_sequence_role(setup) is SequenceRole.NEARBY


def test_chase_breach_has_precedence_without_rewriting_execution_flag() -> None:
    setup = _setup(
        "chased",
        cmp=103.0,
        executable=True,
        entry_status=EntryStatus.READY_NOW,
    )

    diagnostics = build_cmp_actionability_diagnostics(setup)

    assert diagnostics.state is CmpActionabilityState.CHASE_BREACHED
    assert diagnostics.execution_allowed_now is True
    assert classify_setup_sequence_role(setup) is SequenceRole.CURRENT


def test_legacy_late_status_is_reported_as_chase_breached() -> None:
    setup = _setup(
        "late",
        executable=False,
        entry_status=EntryStatus.LATE_OR_CHASING,
    )

    assert build_cmp_actionability_diagnostics(setup).state is CmpActionabilityState.CHASE_BREACHED


def test_invalidated_status_has_highest_diagnostic_precedence() -> None:
    setup = _setup(
        "invalidated",
        cmp=103.0,
        executable=False,
        entry_status=EntryStatus.INVALIDATED,
    )

    assert build_cmp_actionability_diagnostics(setup).state is CmpActionabilityState.INVALIDATED


def test_modes_serialize_identical_actionability_for_same_fixed_slot() -> None:
    setup = _setup("current", executable=True, entry_status=EntryStatus.READY_NOW)

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

    scan_payload = opportunity_portfolio_payload(scan)["current_long"]
    analyze_payload = opportunity_portfolio_payload(analyze)["current_long"]

    assert scan_payload is not None
    assert analyze_payload is not None
    assert scan_payload["cmp_actionability"] == analyze_payload["cmp_actionability"]
    assert scan_payload["cmp_actionability"] == {
        "state": "executable_at_cmp",
        "source_entry_status": "READY_NOW",
        "execution_allowed_now": True,
        "location_state": "inside_entry_zone",
    }
