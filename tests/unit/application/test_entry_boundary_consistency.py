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
    EntryBoundaryConsistencyCode,
    build_entry_boundary_consistency_audit,
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
    direction: TradeDirection = TradeDirection.LONG,
    cmp: float = 100.0,
    lower: float = 99.0,
    upper: float = 101.0,
    preferred: float = 100.0,
    maximum_chase: float = 102.0,
    executable: bool = True,
    entry_status: EntryStatus = EntryStatus.READY_NOW,
) -> DiscoverySetup:
    stop = 97.0 if direction is TradeDirection.LONG else 103.0
    target = 106.0 if direction is TradeDirection.LONG else 94.0
    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=direction,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=entry_status,
        decision_time=NOW,
        candidate_id=candidate_id,
        confidence_score=70.0,
        entry=ActionableEntry(
            lower,
            upper,
            preferred,
            cmp,
            maximum_chase,
            lower <= cmp <= upper,
        ),
        stop_loss=StopLoss(stop, 3.0, 3.0, ("structure",)),
        take_profits=(TakeProfit("TP1", target, 6.0, 2.0, ("liquidity",)),),
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


def test_valid_long_boundaries_have_no_findings() -> None:
    audit = build_entry_boundary_consistency_audit(_setup("valid-long"))

    assert audit.is_consistent is True
    assert audit.codes == ()
    assert audit.ideal_entry_inside_zone is True
    assert audit.maximum_chase_directionally_valid is True


def test_valid_short_boundaries_have_no_findings() -> None:
    setup = _setup(
        "valid-short",
        direction=TradeDirection.SHORT,
        maximum_chase=98.0,
    )

    audit = build_entry_boundary_consistency_audit(setup)

    assert audit.is_consistent is True
    assert audit.codes == ()


def test_existing_contracts_guarantee_core_entry_boundary_invariants() -> None:
    long_audit = build_entry_boundary_consistency_audit(_setup("valid-long"))
    short_audit = build_entry_boundary_consistency_audit(
        _setup(
            "valid-short",
            direction=TradeDirection.SHORT,
            maximum_chase=98.0,
        )
    )

    assert long_audit.ideal_entry_inside_zone is True
    assert long_audit.maximum_chase_directionally_valid is True
    assert short_audit.ideal_entry_inside_zone is True
    assert short_audit.maximum_chase_directionally_valid is True


def test_equal_ideal_and_chase_boundary_is_reported_when_contract_valid() -> None:
    audit = build_entry_boundary_consistency_audit(
        _setup(
            "same-boundary",
            lower=99.0,
            upper=100.0,
            preferred=100.0,
            maximum_chase=100.0,
        )
    )

    assert EntryBoundaryConsistencyCode.MAXIMUM_CHASE_EQUALS_IDEAL_ENTRY in audit.codes


def test_chase_and_late_status_mismatches_are_reported_deterministically() -> None:
    breached = build_entry_boundary_consistency_audit(
        _setup("breached", cmp=103.0, entry_status=EntryStatus.READY_NOW)
    )
    stale_late = build_entry_boundary_consistency_audit(
        _setup(
            "stale-late",
            cmp=100.0,
            executable=False,
            entry_status=EntryStatus.LATE_OR_CHASING,
        )
    )

    assert breached.codes == (EntryBoundaryConsistencyCode.CHASE_BREACHED_WITHOUT_LATE_STATUS,)
    assert stale_late.codes == (EntryBoundaryConsistencyCode.LATE_STATUS_WITHOUT_CHASE_BREACH,)


def test_entry_boundary_audit_serializes_additively() -> None:
    setup = _setup("serialized")
    portfolio = portfolio_from_setups(
        (setup,),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )

    payload = opportunity_portfolio_payload(portfolio)["current_long"]

    assert payload is not None
    assert payload["entry_boundary_consistency"] == {
        "is_consistent": True,
        "codes": [],
        "ideal_entry_inside_zone": True,
        "maximum_chase_directionally_valid": True,
        "maximum_chase_equals_ideal_entry": False,
        "beyond_maximum_chase": False,
        "source_entry_status": "READY_NOW",
    }
    assert payload["entry_zone"]["preferred"] == 100.0
    assert payload["entry_zone"]["maximum_chase"] == 102.0


def test_scan_and_analyze_serialize_identical_boundary_findings() -> None:
    setup = _setup("parity", cmp=103.0)
    scan = portfolio_from_setups(
        (setup,),
        symbol="BTCUSDT",
        cmp=103.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )
    analyze = portfolio_from_setups(
        (replace(setup),),
        symbol="BTCUSDT",
        cmp=103.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    scan_payload = opportunity_portfolio_payload(scan)["current_long"]
    analyze_payload = opportunity_portfolio_payload(analyze)["current_long"]

    assert scan_payload is not None
    assert analyze_payload is not None
    assert (
        scan_payload["entry_boundary_consistency"] == analyze_payload["entry_boundary_consistency"]
    )
