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
    ActionabilityState,
    AnalysisMode,
    CmpEntryAssessmentState,
    SequenceRole,
    SetupExistenceState,
    TriggerFreshnessState,
    build_actionability_state_assessment,
    build_cmp_entry_assessment,
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
    direction: TradeDirection = TradeDirection.LONG,
    cmp: float = 100.0,
    executable: bool,
    entry_status: EntryStatus,
    expiry_seconds: int | None = None,
    expiry_reason: str = "",
) -> DiscoverySetup:
    if direction is TradeDirection.LONG:
        entry = ActionableEntry(
            99.0,
            101.0,
            100.0,
            cmp,
            102.0,
            99.0 <= cmp <= 101.0,
        )
        stop = StopLoss(97.0, 3.0, 3.0, ("structure",))
        targets = (TakeProfit("TP1", 106.0, 6.0, 2.0, ("liquidity",)),)
    else:
        entry = ActionableEntry(
            99.0,
            101.0,
            100.0,
            cmp,
            98.0,
            99.0 <= cmp <= 101.0,
        )
        stop = StopLoss(103.0, 3.0, 3.0, ("structure",))
        targets = (TakeProfit("TP1", 94.0, 6.0, 2.0, ("liquidity",)),)

    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=direction,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=entry_status,
        decision_time=NOW,
        candidate_id=candidate_id,
        confidence_score=70.0,
        entry=entry,
        stop_loss=stop,
        take_profits=targets,
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


def test_current_and_nearby_truth_remains_legacy_compatible() -> None:
    current = _setup(
        "current",
        executable=True,
        entry_status=EntryStatus.READY_NOW,
    )
    nearby = _setup(
        "nearby",
        executable=False,
        entry_status=EntryStatus.PULLBACK_PREFERRED,
    )

    assert classify_setup_sequence_role(current) is SequenceRole.CURRENT
    assert classify_setup_sequence_role(nearby) is SequenceRole.NEARBY
    assert current.execution_allowed_now is True
    assert nearby.execution_allowed_now is False


def test_no_cmp_entry_does_not_erase_structurally_valid_setup() -> None:
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


def test_chased_setup_is_missed_without_moving_entry_geometry() -> None:
    setup = _setup(
        "chased",
        cmp=103.0,
        executable=True,
        entry_status=EntryStatus.READY_NOW,
    )

    actionability = build_actionability_state_assessment(
        setup,
        sequence_role=SequenceRole.CURRENT,
    )

    assert actionability.state is ActionabilityState.MISSED_OR_CHASING
    assert setup.entry.lower == 99.0
    assert setup.entry.upper == 101.0
    assert setup.entry.preferred == 100.0
    assert setup.entry.maximum_chase_price == 102.0
    assert setup.execution_allowed_now is True


def test_stale_trigger_is_visible_without_slot_movement() -> None:
    setup = _setup(
        "stale",
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
    assert portfolio.current_long is not None
    assert portfolio.nearby_long is None
    assert setup.execution_allowed_now is True


def test_invalidated_setup_remains_diagnostically_explicit() -> None:
    setup = _setup(
        "invalidated",
        executable=True,
        entry_status=EntryStatus.INVALIDATED,
    )

    existence = build_setup_existence_assessment(setup)
    cmp_assessment = build_cmp_entry_assessment(
        setup,
        setup_existence=existence,
    )
    actionability = build_actionability_state_assessment(
        setup,
        sequence_role=SequenceRole.CURRENT,
    )

    assert existence.state is SetupExistenceState.INVALIDATED
    assert existence.setup_exists is False
    assert cmp_assessment.state is CmpEntryAssessmentState.SETUP_INVALIDATED
    assert actionability.state is ActionabilityState.INVALIDATED
    assert setup.execution_allowed_now is True


def test_long_and_short_use_directional_chase_boundaries() -> None:
    long_setup = _setup(
        "long-chased",
        direction=TradeDirection.LONG,
        cmp=103.0,
        executable=True,
        entry_status=EntryStatus.READY_NOW,
    )
    short_setup = _setup(
        "short-chased",
        direction=TradeDirection.SHORT,
        cmp=97.0,
        executable=True,
        entry_status=EntryStatus.READY_NOW,
    )

    long_state = build_actionability_state_assessment(
        long_setup,
        sequence_role=SequenceRole.CURRENT,
    )
    short_state = build_actionability_state_assessment(
        short_setup,
        sequence_role=SequenceRole.CURRENT,
    )

    assert long_state.state is ActionabilityState.MISSED_OR_CHASING
    assert short_state.state is ActionabilityState.MISSED_OR_CHASING


def test_scan_and_analyze_fixed_slot_payloads_are_identical() -> None:
    setup = _setup(
        "mode-parity",
        executable=True,
        entry_status=EntryStatus.READY_NOW,
        expiry_seconds=60,
        expiry_reason="micro trigger window",
    )

    scan = portfolio_from_setups(
        (setup,),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW + timedelta(seconds=30),
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )
    analyze = portfolio_from_setups(
        (replace(setup),),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW + timedelta(seconds=30),
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    scan_payload = opportunity_portfolio_payload(scan)["current_long"]
    analyze_payload = opportunity_portfolio_payload(analyze)["current_long"]

    assert scan_payload is not None
    assert analyze_payload is not None
    assert scan_payload == analyze_payload


def test_repeated_serialization_is_deterministic() -> None:
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
