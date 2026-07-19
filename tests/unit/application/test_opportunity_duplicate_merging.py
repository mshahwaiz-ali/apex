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
from apex.application.opportunity_portfolio import AnalysisMode, portfolio_from_setups
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _setup(candidate_id: str) -> DiscoverySetup:
    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=EntryStatus.READY_NOW,
        decision_time=NOW,
        candidate_id=candidate_id,
        confidence_score=70.0,
        entry=ActionableEntry(99.0, 101.0, 100.0, 100.0, 102.0, True),
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
        execution_allowed_now=True,
    )


def test_different_candidate_ids_with_identical_thesis_are_merged() -> None:
    first = _setup("strategy-a")
    duplicate_thesis = replace(first, candidate_id="strategy-b")

    portfolio = portfolio_from_setups(
        (first, duplicate_thesis),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert portfolio.current_long is not None
    assert portfolio.current_long.opportunity_id == "strategy-a"
    assert portfolio.follow_up_opportunities == ()
    assert len(portfolio.opportunities) == 1


def test_distinct_geometry_is_not_merged() -> None:
    first = _setup("strategy-a")
    distinct = replace(
        first,
        candidate_id="strategy-b",
        entry=ActionableEntry(97.0, 98.0, 97.5, 100.0, 99.0, False),
        stop_loss=StopLoss(95.0, 2.5, 2.5, ("deeper_structure",)),
        execution_allowed_now=False,
        entry_status=EntryStatus.PULLBACK_PREFERRED,
    )

    portfolio = portfolio_from_setups(
        (first, distinct),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert portfolio.current_long is not None
    assert portfolio.nearby_long is not None
    assert len(portfolio.opportunities) == 2


def test_opposite_direction_is_never_merged() -> None:
    long_setup = _setup("long")
    short_setup = replace(
        long_setup,
        candidate_id="short",
        direction=TradeDirection.SHORT,
        entry=ActionableEntry(99.0, 101.0, 100.0, 100.0, 98.0, True),
        stop_loss=StopLoss(103.0, 3.0, 3.0, ("structure",)),
        take_profits=(TakeProfit("TP1", 94.0, 6.0, 2.0, ("liquidity",)),),
    )

    portfolio = portfolio_from_setups(
        (long_setup, short_setup),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert portfolio.current_long is not None
    assert portfolio.current_short is not None
    assert len(portfolio.opportunities) == 2
