from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

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
    ActionabilityState,
    AnalysisMode,
    CmpEntryAssessmentState,
    EntryBoundaryConsistencyCode,
    SequenceRole,
    SetupExistenceState,
    StaleTriggerDiagnosticCode,
    TriggerFreshnessState,
    build_actionability_consistency_audit,
    build_actionability_state_assessment,
    build_cmp_distance_diagnostics,
    build_cmp_entry_assessment,
    build_entry_boundary_consistency_audit,
    build_setup_existence_assessment,
    build_stale_trigger_diagnostics,
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
    executable: bool,
    entry_status: EntryStatus,
    expiry_seconds: int | None = None,
    expiry_reason: str = "",
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
            99.0,
            101.0,
            100.0,
            cmp,
            102.0,
            99.0 <= cmp <= 101.0,
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
        setup_expiry_seconds=expiry_seconds,
        setup_expiry_reason=expiry_reason,
    )


def test_valid_current_setup_is_consistent_across_all_batch5_layers() -> None:
    setup = _setup(
        "valid-current",
        executable=True,
        entry_status=EntryStatus.READY_NOW,
        expiry_seconds=60,
        expiry_reason="micro trigger window",
    )
    role = classify_setup_sequence_role(setup)
    distance = build_cmp_distance_diagnostics(setup)
    consistency = build_actionability_consistency_audit(
        setup,
        sequence_role=role,
        cmp_distance=distance,
    )
    actionability = build_actionability_state_assessment(
        setup,
        sequence_role=role,
        cmp_distance=distance,
    )
    existence = build_setup_existence_assessment(setup)
    cmp_assessment = build_cmp_entry_assessment(
        setup,
        cmp_distance=distance,
        setup_existence=existence,
    )
    boundaries = build_entry_boundary_consistency_audit(
        setup,
        cmp_distance=distance,
    )
    freshness = build_stale_trigger_diagnostics(
        setup,
        evaluated_at=NOW + timedelta(seconds=30),
    )

    assert role is SequenceRole.CURRENT
    assert consistency.is_consistent is True
    assert actionability.state is ActionabilityState.EXECUTE_NOW
    assert existence.state is SetupExistenceState.STRUCTURALLY_VALID
    assert cmp_assessment.state is CmpEntryAssessmentState.AVAILABLE_NOW
    assert boundaries.is_consistent is True
    assert freshness.state is TriggerFreshnessState.FRESH


def test_nearby_setup_exists_even_when_cmp_execution_is_unavailable() -> None:
    setup = _setup(
        "nearby",
        executable=False,
        entry_status=EntryStatus.PULLBACK_PREFERRED,
    )
    role = classify_setup_sequence_role(setup)
    existence = build_setup_existence_assessment(setup)
    cmp_assessment = build_cmp_entry_assessment(setup)
    actionability = build_actionability_state_assessment(
        setup,
        sequence_role=role,
    )

    assert role is SequenceRole.NEARBY
    assert existence.setup_exists is True
    assert existence.state is SetupExistenceState.STRUCTURALLY_VALID
    assert cmp_assessment.state is CmpEntryAssessmentState.NOT_AVAILABLE_NEARBY_SETUP
    assert actionability.state is ActionabilityState.RETEST_PREFERRED


def test_chase_breach_is_visible_without_rewriting_legacy_execution_truth() -> None:
    setup = _setup(
        "chased",
        cmp=103.0,
        executable=True,
        entry_status=EntryStatus.READY_NOW,
    )
    role = classify_setup_sequence_role(setup)
    distance = build_cmp_distance_diagnostics(setup)
    consistency = build_actionability_consistency_audit(
        setup,
        sequence_role=role,
        cmp_distance=distance,
    )
    actionability = build_actionability_state_assessment(
        setup,
        sequence_role=role,
        cmp_distance=distance,
    )
    cmp_assessment = build_cmp_entry_assessment(
        setup,
        cmp_distance=distance,
    )
    boundaries = build_entry_boundary_consistency_audit(
        setup,
        cmp_distance=distance,
    )

    assert setup.execution_allowed_now is True
    assert role is SequenceRole.CURRENT
    assert actionability.state is ActionabilityState.MISSED_OR_CHASING
    assert cmp_assessment.state is CmpEntryAssessmentState.MISSED_OR_CHASING
    assert consistency.codes == (
        ActionabilityConsistencyCode.CHASE_BREACHED_EXECUTION_AUTHORIZED,
        ActionabilityConsistencyCode.READY_NOW_OUTSIDE_ENTRY_ZONE,
    )
    assert boundaries.codes == (EntryBoundaryConsistencyCode.CHASE_BREACHED_WITHOUT_LATE_STATUS,)


def test_invalidated_status_has_precedence_without_silent_correction() -> None:
    setup = _setup(
        "invalidated",
        executable=True,
        entry_status=EntryStatus.INVALIDATED,
    )
    role = classify_setup_sequence_role(setup)
    existence = build_setup_existence_assessment(setup)
    cmp_assessment = build_cmp_entry_assessment(
        setup,
        setup_existence=existence,
    )
    actionability = build_actionability_state_assessment(
        setup,
        sequence_role=role,
    )
    consistency = build_actionability_consistency_audit(
        setup,
        sequence_role=role,
    )

    assert setup.execution_allowed_now is True
    assert role is SequenceRole.CURRENT
    assert existence.state is SetupExistenceState.INVALIDATED
    assert existence.setup_exists is False
    assert cmp_assessment.state is CmpEntryAssessmentState.SETUP_INVALIDATED
    assert actionability.state is ActionabilityState.INVALIDATED
    assert consistency.codes == (
        ActionabilityConsistencyCode.INVALIDATED_EXECUTION_AUTHORIZED,
        ActionabilityConsistencyCode.NON_IMMEDIATE_STATUS_EXECUTION_AUTHORIZED,
    )


def test_stale_trigger_is_diagnostic_only_and_preserves_current_slot() -> None:
    setup = _setup(
        "stale-current",
        executable=True,
        entry_status=EntryStatus.READY_NOW,
        expiry_seconds=30,
        expiry_reason="activation expired",
    )
    evaluated_at = NOW + timedelta(seconds=31)
    freshness = build_stale_trigger_diagnostics(
        setup,
        evaluated_at=evaluated_at,
    )
    portfolio = portfolio_from_setups(
        (setup,),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=evaluated_at,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )

    assert freshness.state is TriggerFreshnessState.STALE
    assert freshness.codes == (
        StaleTriggerDiagnosticCode.EXPIRED_BY_SECONDS,
        StaleTriggerDiagnosticCode.EXECUTION_AUTHORIZED_AFTER_EXPIRY,
    )
    assert setup.execution_allowed_now is True
    assert portfolio.current_long is not None
    assert portfolio.nearby_long is None


def test_scan_and_analyze_preserve_identical_fixed_slot_truth() -> None:
    setup = _setup(
        "mode-parity",
        cmp=103.0,
        executable=True,
        entry_status=EntryStatus.READY_NOW,
        expiry_seconds=30,
        expiry_reason="activation expired",
    )
    evaluated_at = NOW + timedelta(seconds=31)
    scan = portfolio_from_setups(
        (setup,),
        symbol="BTCUSDT",
        cmp=103.0,
        analysis_timestamp=evaluated_at,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )
    analyze = portfolio_from_setups(
        (replace(setup),),
        symbol="BTCUSDT",
        cmp=103.0,
        analysis_timestamp=evaluated_at,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    scan_payload = opportunity_portfolio_payload(scan)["current_long"]
    analyze_payload = opportunity_portfolio_payload(analyze)["current_long"]

    assert scan_payload is not None
    assert analyze_payload is not None
    assert scan_payload == analyze_payload


def test_repeated_identical_inputs_produce_identical_diagnostics() -> None:
    setup = _setup(
        "deterministic",
        cmp=103.0,
        executable=True,
        entry_status=EntryStatus.READY_NOW,
        expiry_seconds=30,
        expiry_reason="activation expired",
    )
    evaluated_at = NOW + timedelta(seconds=31)

    first = opportunity_portfolio_payload(
        portfolio_from_setups(
            (setup,),
            symbol="BTCUSDT",
            cmp=103.0,
            analysis_timestamp=evaluated_at,
            analysis_mode=AnalysisMode.ANALYZE_FULL,
        )
    )
    second = opportunity_portfolio_payload(
        portfolio_from_setups(
            (replace(setup),),
            symbol="BTCUSDT",
            cmp=103.0,
            analysis_timestamp=evaluated_at,
            analysis_mode=AnalysisMode.ANALYZE_FULL,
        )
    )

    assert first == second
