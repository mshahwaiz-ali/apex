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
    ActionabilityConsistencyCode,
    AnalysisMode,
    SequenceRole,
    build_actionability_consistency_audit,
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


def test_valid_ready_now_combination_has_no_consistency_findings() -> None:
    setup = _setup(
        "valid-current",
        executable=True,
        entry_status=EntryStatus.READY_NOW,
    )

    audit = build_actionability_consistency_audit(
        setup,
        sequence_role=SequenceRole.CURRENT,
    )

    assert audit.is_consistent is True
    assert audit.codes == ()


def test_ready_now_outside_zone_is_reported_without_changing_source_facts() -> None:
    setup = _setup(
        "outside-zone",
        cmp=98.0,
        executable=True,
        entry_status=EntryStatus.READY_NOW,
    )

    audit = build_actionability_consistency_audit(
        setup,
        sequence_role=SequenceRole.CURRENT,
    )

    assert audit.codes == (ActionabilityConsistencyCode.READY_NOW_OUTSIDE_ENTRY_ZONE,)
    assert audit.execution_allowed_now is True
    assert audit.sequence_role is SequenceRole.CURRENT


def test_chase_breach_and_authorized_execution_have_deterministic_findings() -> None:
    setup = _setup(
        "chased-current",
        cmp=103.0,
        executable=True,
        entry_status=EntryStatus.READY_NOW,
    )

    audit = build_actionability_consistency_audit(
        setup,
        sequence_role=SequenceRole.CURRENT,
    )

    assert audit.codes == (
        ActionabilityConsistencyCode.CHASE_BREACHED_EXECUTION_AUTHORIZED,
        ActionabilityConsistencyCode.READY_NOW_OUTSIDE_ENTRY_ZONE,
    )


def test_invalidated_but_authorized_execution_reports_both_status_conflicts() -> None:
    setup = _setup(
        "invalidated-current",
        executable=True,
        entry_status=EntryStatus.INVALIDATED,
    )

    audit = build_actionability_consistency_audit(
        setup,
        sequence_role=SequenceRole.CURRENT,
    )

    assert audit.codes == (
        ActionabilityConsistencyCode.INVALIDATED_EXECUTION_AUTHORIZED,
        ActionabilityConsistencyCode.NON_IMMEDIATE_STATUS_EXECUTION_AUTHORIZED,
    )


def test_immediate_status_with_disabled_execution_is_reported() -> None:
    setup = _setup(
        "disabled-ready",
        executable=False,
        entry_status=EntryStatus.READY_NOW,
    )

    audit = build_actionability_consistency_audit(
        setup,
        sequence_role=SequenceRole.NEARBY,
    )

    assert audit.codes == (ActionabilityConsistencyCode.IMMEDIATE_STATUS_EXECUTION_DISABLED,)


def test_explicit_role_authorization_contradictions_are_auditable() -> None:
    executable = _setup(
        "nearby-authorized",
        executable=True,
        entry_status=EntryStatus.READY_NOW,
    )
    disabled = _setup(
        "current-disabled",
        executable=False,
        entry_status=EntryStatus.PULLBACK_PREFERRED,
    )

    nearby_audit = build_actionability_consistency_audit(
        executable,
        sequence_role=SequenceRole.NEARBY,
    )
    current_audit = build_actionability_consistency_audit(
        disabled,
        sequence_role=SequenceRole.CURRENT,
    )

    assert nearby_audit.codes == (ActionabilityConsistencyCode.NEARBY_ROLE_EXECUTION_AUTHORIZED,)
    assert current_audit.codes == (ActionabilityConsistencyCode.CURRENT_ROLE_EXECUTION_DISABLED,)


def test_consistency_audit_is_serialized_additively() -> None:
    setup = _setup(
        "serialized-conflict",
        cmp=103.0,
        executable=True,
        entry_status=EntryStatus.READY_NOW,
    )
    portfolio = portfolio_from_setups(
        (setup,),
        symbol="BTCUSDT",
        cmp=103.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )

    payload = opportunity_portfolio_payload(portfolio)["current_long"]

    assert payload is not None
    assert payload["actionability_consistency"] == {
        "is_consistent": False,
        "codes": [
            "chase_breached_execution_authorized",
            "ready_now_outside_entry_zone",
        ],
        "source_entry_status": "READY_NOW",
        "execution_allowed_now": True,
        "location_state": "beyond_maximum_chase",
        "beyond_maximum_chase": True,
        "sequence_role": "current",
    }
    assert payload["entry_status"] == "READY_NOW"
    assert payload["execution_allowed_now"] is True
    assert payload["sequence_role"] == "current"


def test_scan_and_analyze_serialize_identical_consistency_findings() -> None:
    setup = _setup(
        "mode-parity",
        cmp=103.0,
        executable=True,
        entry_status=EntryStatus.READY_NOW,
    )

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
    assert scan_payload["actionability_consistency"] == analyze_payload["actionability_consistency"]
