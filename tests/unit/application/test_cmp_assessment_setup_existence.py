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
    CmpEntryAssessmentState,
    SetupExistenceState,
    build_cmp_entry_assessment,
    build_setup_existence_assessment,
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


def test_no_cmp_entry_does_not_mean_no_setup() -> None:
    setup = _setup(
        "nearby-valid",
        executable=False,
        entry_status=EntryStatus.PULLBACK_PREFERRED,
    )

    existence = build_setup_existence_assessment(setup)
    cmp_assessment = build_cmp_entry_assessment(
        setup,
        setup_existence=existence,
    )

    assert existence.state is SetupExistenceState.STRUCTURALLY_VALID
    assert existence.setup_exists is True
    assert cmp_assessment.state is CmpEntryAssessmentState.NOT_AVAILABLE_NEARBY_SETUP
    assert cmp_assessment.setup_existence_state is SetupExistenceState.STRUCTURALLY_VALID


def test_available_cmp_entry_and_setup_existence_are_independent_facts() -> None:
    setup = _setup(
        "current-valid",
        executable=True,
        entry_status=EntryStatus.READY_NOW,
    )

    existence = build_setup_existence_assessment(setup)
    cmp_assessment = build_cmp_entry_assessment(
        setup,
        setup_existence=existence,
    )

    assert existence.state is SetupExistenceState.STRUCTURALLY_VALID
    assert cmp_assessment.state is CmpEntryAssessmentState.AVAILABLE_NOW


def test_poor_cmp_location_preserves_setup_existence() -> None:
    setup = _setup(
        "poor-location",
        cmp=98.0,
        executable=True,
        entry_status=EntryStatus.READY_NOW,
    )

    existence = build_setup_existence_assessment(setup)
    cmp_assessment = build_cmp_entry_assessment(
        setup,
        setup_existence=existence,
    )

    assert existence.setup_exists is True
    assert cmp_assessment.state is CmpEntryAssessmentState.AVAILABLE_BUT_POOR_LOCATION


def test_chased_cmp_entry_preserves_underlying_setup_diagnostic() -> None:
    setup = _setup(
        "chased",
        cmp=103.0,
        executable=True,
        entry_status=EntryStatus.READY_NOW,
    )

    existence = build_setup_existence_assessment(setup)
    cmp_assessment = build_cmp_entry_assessment(
        setup,
        setup_existence=existence,
    )

    assert existence.state is SetupExistenceState.STRUCTURALLY_VALID
    assert cmp_assessment.state is CmpEntryAssessmentState.MISSED_OR_CHASING


def test_invalidated_setup_is_not_reported_as_nearby() -> None:
    setup = _setup(
        "invalidated",
        executable=False,
        entry_status=EntryStatus.INVALIDATED,
    )

    existence = build_setup_existence_assessment(setup)
    cmp_assessment = build_cmp_entry_assessment(
        setup,
        setup_existence=existence,
    )

    assert existence.state is SetupExistenceState.INVALIDATED
    assert existence.setup_exists is False
    assert cmp_assessment.state is CmpEntryAssessmentState.SETUP_INVALIDATED


def test_cmp_and_setup_assessments_serialize_additively() -> None:
    setup = _setup(
        "serialized",
        executable=False,
        entry_status=EntryStatus.PULLBACK_PREFERRED,
    )
    portfolio = portfolio_from_setups(
        (setup,),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )

    payload = opportunity_portfolio_payload(portfolio)["nearby_long"]

    assert payload is not None
    assert payload["setup_existence"] == {
        "state": "structurally_valid",
        "source_entry_status": "PULLBACK_PREFERRED",
        "setup_exists": True,
    }
    assert payload["cmp_entry_assessment"] == {
        "state": "not_available_nearby_setup",
        "execution_allowed_now": False,
        "location_state": "inside_entry_zone",
        "beyond_maximum_chase": False,
        "setup_existence_state": "structurally_valid",
    }
    assert payload["execution_allowed_now"] is False
    assert payload["sequence_role"] == "nearby"


def test_scan_and_analyze_serialize_identical_cmp_and_setup_truth() -> None:
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
    assert scan_payload["setup_existence"] == analyze_payload["setup_existence"]
    assert scan_payload["cmp_entry_assessment"] == analyze_payload["cmp_entry_assessment"]
