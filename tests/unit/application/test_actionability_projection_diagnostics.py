from __future__ import annotations

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
    ActionabilityProjectionIssue,
    AnalysisMode,
    SequenceRole,
    build_actionability_consistency_audit,
    build_actionability_state_assessment,
    build_cmp_distance_diagnostics,
    build_entry_boundary_consistency_audit,
    build_stale_trigger_diagnostics,
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
    executable: bool = True,
    entry_status: EntryStatus = EntryStatus.READY_NOW,
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


def test_clean_projection_has_no_issues() -> None:
    setup = _setup("clean")
    distance = build_cmp_distance_diagnostics(setup)
    consistency = build_actionability_consistency_audit(
        setup,
        sequence_role=SequenceRole.CURRENT,
        cmp_distance=distance,
    )
    boundaries = build_entry_boundary_consistency_audit(
        setup,
        cmp_distance=distance,
    )
    freshness = build_stale_trigger_diagnostics(setup, evaluated_at=NOW)

    result = build_actionability_state_assessment(
        setup,
        sequence_role=SequenceRole.CURRENT,
        cmp_distance=distance,
        consistency_audit=consistency,
        stale_trigger=freshness,
        entry_boundary_audit=boundaries,
    )

    assert result.issues == ()
    assert result.has_blocking_issue is False


def test_actionability_contradiction_is_attached_without_state_rewrite() -> None:
    setup = _setup("conflict", cmp=98.0)
    distance = build_cmp_distance_diagnostics(setup)
    consistency = build_actionability_consistency_audit(
        setup,
        sequence_role=SequenceRole.CURRENT,
        cmp_distance=distance,
    )

    result = build_actionability_state_assessment(
        setup,
        sequence_role=SequenceRole.CURRENT,
        cmp_distance=distance,
        consistency_audit=consistency,
    )

    assert result.state.value == "cmp_available_but_poor_location"
    assert result.issues == (ActionabilityProjectionIssue.ACTIONABILITY_CONTRADICTION,)
    assert result.has_blocking_issue is True
    assert result.execution_allowed_now is True


def test_stale_trigger_is_blocking_but_does_not_change_legacy_state() -> None:
    setup = _setup(
        "stale",
        expiry_seconds=30,
        expiry_reason="activation expired",
    )
    freshness = build_stale_trigger_diagnostics(
        setup,
        evaluated_at=NOW + timedelta(seconds=31),
    )

    result = build_actionability_state_assessment(
        setup,
        sequence_role=SequenceRole.CURRENT,
        stale_trigger=freshness,
    )

    assert result.state.value == "execute_now"
    assert result.issues == (ActionabilityProjectionIssue.STALE_TRIGGER,)
    assert result.has_blocking_issue is True
    assert result.execution_allowed_now is True


def test_bar_expiry_unevaluated_is_non_blocking_uncertainty() -> None:
    base = _setup("bar-expiry")
    setup = DiscoverySetup(
        symbol=base.symbol,
        direction=base.direction,
        strategy=base.strategy,
        entry_status=base.entry_status,
        decision_time=base.decision_time,
        candidate_id=base.candidate_id,
        confidence_score=base.confidence_score,
        entry=base.entry,
        stop_loss=base.stop_loss,
        take_profits=base.take_profits,
        management_policies=base.management_policies,
        execution_allowed_now=base.execution_allowed_now,
        setup_expiry_bars=3,
    )
    freshness = build_stale_trigger_diagnostics(
        setup,
        evaluated_at=NOW + timedelta(minutes=5),
    )

    result = build_actionability_state_assessment(
        setup,
        sequence_role=SequenceRole.CURRENT,
        stale_trigger=freshness,
    )

    assert result.issues == (ActionabilityProjectionIssue.BAR_EXPIRY_UNEVALUATED,)
    assert result.has_blocking_issue is False


def test_serialized_projection_contains_integrated_diagnostics() -> None:
    setup = _setup(
        "serialized",
        expiry_seconds=30,
        expiry_reason="activation expired",
    )
    evaluated_at = NOW + timedelta(seconds=31)
    portfolio = portfolio_from_setups(
        (setup,),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=evaluated_at,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )

    payload = opportunity_portfolio_payload(portfolio)["current_long"]

    assert payload is not None
    assert payload["actionability_state"]["state"] == "execute_now"
    assert payload["actionability_state"]["issues"] == ["stale_trigger"]
    assert payload["actionability_state"]["has_blocking_issue"] is True
    assert payload["execution_allowed_now"] is True
    assert payload["sequence_role"] == "current"
