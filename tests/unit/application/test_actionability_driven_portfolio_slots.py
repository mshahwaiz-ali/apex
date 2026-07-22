from __future__ import annotations

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
    AnalysisMode,
    SequenceRole,
    TradeOpportunity,
    classify_setup_sequence_role,
    portfolio_from_setups,
)
from apex.strategies.contracts import EntryMode, TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _setup(
    candidate_id: str,
    *,
    current_price: float,
    entry_mode: EntryMode,
    confirmation_complete: bool,
    execution_allowed_now: bool = False,
    entry_status: EntryStatus = EntryStatus.WATCH_NEAR_ENTRY,
) -> DiscoverySetup:
    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=entry_status,
        decision_time=NOW,
        candidate_id=candidate_id,
        confidence_score=75.0,
        entry=ActionableEntry(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=current_price,
            maximum_chase_price=102.0,
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
        entry_mode=entry_mode,
        confirmation_required=not confirmation_complete,
        confirmation_complete=confirmation_complete,
        canonical_actionability=True,
    )


def test_aggressive_inside_zone_is_current_without_legacy_execution_flag() -> None:
    setup = _setup(
        "aggressive",
        current_price=100.0,
        entry_mode=EntryMode.MARKET_NEAR,
        confirmation_complete=False,
    )

    assert classify_setup_sequence_role(setup) is SequenceRole.CURRENT
    opportunity = TradeOpportunity(setup.candidate_id, setup, SequenceRole.CURRENT)
    assert opportunity.sequence_role is SequenceRole.CURRENT


def test_micro_confirmation_inside_zone_is_current() -> None:
    setup = _setup(
        "micro",
        current_price=100.0,
        entry_mode=EntryMode.RETEST,
        confirmation_complete=False,
        entry_status=EntryStatus.PULLBACK_PREFERRED,
    )

    assert classify_setup_sequence_role(setup) is SequenceRole.CURRENT


def test_place_limit_outside_zone_is_nearby() -> None:
    setup = _setup(
        "limit",
        current_price=98.0,
        entry_mode=EntryMode.PULLBACK,
        confirmation_complete=False,
        entry_status=EntryStatus.PULLBACK_PREFERRED,
    )

    assert classify_setup_sequence_role(setup) is SequenceRole.NEARBY


def test_legacy_execution_flag_cannot_force_poor_location_into_current_slot() -> None:
    setup = _setup(
        "poor-location",
        current_price=98.0,
        entry_mode=EntryMode.MARKET_NEAR,
        confirmation_complete=True,
        execution_allowed_now=True,
        entry_status=EntryStatus.READY_NOW,
    )

    assert classify_setup_sequence_role(setup) is SequenceRole.NEARBY
    with pytest.raises(ValueError, match="canonical actionability"):
        TradeOpportunity(setup.candidate_id, setup, SequenceRole.CURRENT)


def test_invalidated_setup_is_excluded_but_chased_setup_remains_alert_only() -> None:
    invalidated = _setup(
        "invalidated",
        current_price=96.0,
        entry_mode=EntryMode.MARKET_NEAR,
        confirmation_complete=False,
        entry_status=EntryStatus.WATCH_NEAR_ENTRY,
    )
    chased = _setup(
        "chased",
        current_price=103.0,
        entry_mode=EntryMode.RETEST,
        confirmation_complete=False,
        entry_status=EntryStatus.PULLBACK_PREFERRED,
    )

    portfolio = portfolio_from_setups(
        (invalidated, chased),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert len(portfolio.opportunities) == 1
    assert portfolio.opportunities[0].opportunity_id == "chased"
    assert portfolio.opportunities[0].setup.execution_allowed_now is False


def test_portfolio_places_aggressive_current_and_limit_nearby() -> None:
    aggressive = _setup(
        "aggressive",
        current_price=100.0,
        entry_mode=EntryMode.MARKET_NEAR,
        confirmation_complete=False,
    )
    limit = _setup(
        "limit",
        current_price=98.0,
        entry_mode=EntryMode.PULLBACK,
        confirmation_complete=False,
        entry_status=EntryStatus.PULLBACK_PREFERRED,
    )

    portfolio = portfolio_from_setups(
        (aggressive, limit),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert portfolio.current_long is not None
    assert portfolio.current_long.opportunity_id == "aggressive"
    assert portfolio.nearby_long is not None
    assert portfolio.nearby_long.opportunity_id == "limit"
