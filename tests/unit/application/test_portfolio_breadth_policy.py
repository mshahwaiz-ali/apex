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


def _setup(candidate_id: str, *, executable: bool) -> DiscoverySetup:
    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=EntryStatus.READY_NOW if executable else EntryStatus.PULLBACK_PREFERRED,
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
        execution_allowed_now=executable,
    )


def test_modes_share_fixed_slot_selection_but_differ_in_breadth() -> None:
    primary = _setup("primary", executable=True)
    follow_up = replace(
        primary,
        candidate_id="follow-up",
        entry=ActionableEntry(98.0, 100.0, 99.0, 100.0, 101.0, True),
        stop_loss=StopLoss(96.0, 3.0, 3.0, ("deeper_structure",)),
    )
    setups = (primary, follow_up)

    scan = portfolio_from_setups(
        setups,
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )
    analyze = portfolio_from_setups(
        setups,
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert scan.current_long == analyze.current_long
    assert scan.nearby_long == analyze.nearby_long
    assert scan.current_short == analyze.current_short
    assert scan.nearby_short == analyze.nearby_short
    assert scan.follow_up_opportunities == ()
    assert tuple(item.opportunity_id for item in analyze.follow_up_opportunities) == ("follow-up",)


def test_scan_breadth_does_not_promote_or_reject_candidates() -> None:
    primary = _setup("primary", executable=False)
    extra = replace(primary, candidate_id="extra")

    scan = portfolio_from_setups(
        (primary, extra),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )

    assert scan.nearby_long is not None
    assert scan.nearby_long.opportunity_id == "primary"
    assert scan.current_long is None
    assert scan.follow_up_opportunities == ()
