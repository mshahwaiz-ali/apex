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
    ActionabilityClassificationBasis,
    ActionabilityState,
    SequenceRole,
    TriggerFreshnessState,
    build_actionability_state_assessment,
    build_cmp_distance_diagnostics,
    build_stale_trigger_diagnostics,
)
from apex.strategies.contracts import EntryMode, TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _setup(
    *,
    current_price: float = 100.0,
    maximum_chase: float = 102.0,
    entry_mode: EntryMode = EntryMode.MARKET_NEAR,
    confirmation_complete: bool = True,
    entry_status: EntryStatus = EntryStatus.READY_NOW,
    execution_allowed_now: bool = True,
    expiry_seconds: int | None = 300,
) -> DiscoverySetup:
    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=entry_status,
        decision_time=NOW,
        candidate_id="candidate",
        confidence_score=75.0,
        entry=ActionableEntry(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=current_price,
            maximum_chase_price=maximum_chase,
            current_price_inside_zone=99.0 <= current_price <= 101.0,
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
        execution_allowed_now=execution_allowed_now,
        setup_expiry_seconds=expiry_seconds,
        setup_expiry_reason="fixture expiry" if expiry_seconds is not None else "",
        entry_mode=entry_mode,
        confirmation_required=not confirmation_complete,
        confirmation_complete=confirmation_complete,
        canonical_actionability=True,
    )


def _state(setup: DiscoverySetup) -> tuple[ActionabilityState, ActionabilityClassificationBasis]:
    assessment = build_actionability_state_assessment(
        setup,
        sequence_role=(
            SequenceRole.CURRENT if setup.execution_allowed_now else SequenceRole.NEARBY
        ),
        cmp_distance=build_cmp_distance_diagnostics(setup),
    )
    assert assessment.is_legacy_projection is False
    return assessment.state, assessment.basis


def test_execute_now_requires_cmp_inside_zone_and_complete_confirmation() -> None:
    state, basis = _state(_setup())

    assert state is ActionabilityState.EXECUTE_NOW
    assert basis is ActionabilityClassificationBasis.CONFIRMED_INSIDE_ZONE


def test_inside_zone_market_entry_with_incomplete_confirmation_is_aggressive() -> None:
    state, basis = _state(
        _setup(
            confirmation_complete=False,
            entry_status=EntryStatus.WATCH_NEAR_ENTRY,
            execution_allowed_now=False,
        )
    )

    assert state is ActionabilityState.AGGRESSIVE_NOW
    assert basis is ActionabilityClassificationBasis.AGGRESSIVE_INSIDE_ZONE


def test_inside_zone_retest_waits_for_micro_confirmation() -> None:
    state, basis = _state(
        _setup(
            entry_mode=EntryMode.RETEST,
            confirmation_complete=False,
            entry_status=EntryStatus.PULLBACK_PREFERRED,
            execution_allowed_now=False,
        )
    )

    assert state is ActionabilityState.EXECUTE_ON_MICRO_CONFIRMATION
    assert basis is ActionabilityClassificationBasis.MICRO_CONFIRMATION_INSIDE_ZONE


def test_pullback_outside_zone_is_place_limit() -> None:
    state, basis = _state(
        _setup(
            current_price=98.0,
            entry_mode=EntryMode.PULLBACK,
            confirmation_complete=False,
            entry_status=EntryStatus.PULLBACK_PREFERRED,
            execution_allowed_now=False,
        )
    )

    assert state is ActionabilityState.PLACE_LIMIT
    assert basis is ActionabilityClassificationBasis.LIMIT_ZONE


def test_retest_and_sweep_modes_preserve_distinct_activation_states() -> None:
    retest_state, _ = _state(
        _setup(
            current_price=98.0,
            entry_mode=EntryMode.RETEST,
            confirmation_complete=False,
            execution_allowed_now=False,
        )
    )
    reclaim_state, _ = _state(
        _setup(
            current_price=98.0,
            entry_mode=EntryMode.SWEEP_RECOVERY,
            confirmation_complete=False,
            execution_allowed_now=False,
        )
    )

    assert retest_state is ActionabilityState.RETEST_PREFERRED
    assert reclaim_state is ActionabilityState.RECLAIM_REQUIRED


def test_chase_boundary_precedes_activation_state() -> None:
    state, basis = _state(
        _setup(
            current_price=103.0,
            entry_mode=EntryMode.RETEST,
            confirmation_complete=False,
            entry_status=EntryStatus.PULLBACK_PREFERRED,
            execution_allowed_now=False,
        )
    )

    assert state is ActionabilityState.MISSED_OR_CHASING
    assert basis is ActionabilityClassificationBasis.MAXIMUM_CHASE


def test_structural_stop_breach_is_invalidated_without_legacy_status() -> None:
    setup = _setup(
        current_price=96.0,
        maximum_chase=102.0,
        entry_status=EntryStatus.WATCH_NEAR_ENTRY,
        execution_allowed_now=False,
    )
    state, basis = _state(setup)

    assert state is ActionabilityState.INVALIDATED
    assert basis is ActionabilityClassificationBasis.STRUCTURAL_INVALIDATION


def test_stale_trigger_cannot_remain_executable() -> None:
    setup = replace(
        _setup(
            confirmation_complete=False,
            entry_status=EntryStatus.WATCH_NEAR_ENTRY,
            execution_allowed_now=False,
            expiry_seconds=60,
        ),
        decision_time=datetime(2026, 7, 19, 23, 58, tzinfo=UTC),
    )
    stale = build_stale_trigger_diagnostics(setup, evaluated_at=NOW)
    assessment = build_actionability_state_assessment(
        setup,
        sequence_role=SequenceRole.NEARBY,
        stale_trigger=stale,
    )

    assert stale.state is TriggerFreshnessState.STALE
    assert assessment.state is ActionabilityState.DEVELOPING
    assert assessment.has_blocking_issue is True
    assert assessment.basis is ActionabilityClassificationBasis.STALE_OR_EXPIRED_TRIGGER
