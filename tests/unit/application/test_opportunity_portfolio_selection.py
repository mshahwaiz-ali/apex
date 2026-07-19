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
    SequenceRole,
    portfolio_from_setups,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _setup(candidate_id: str, direction: TradeDirection, *, executable: bool) -> DiscoverySetup:
    if direction is TradeDirection.LONG:
        entry = ActionableEntry(99.0, 101.0, 100.0, 100.0, 102.0, True)
        stop = StopLoss(97.0, 3.0, 3.0, ("structure",))
        target = TakeProfit("TP1", 106.0, 6.0, 2.0, ("liquidity",))
    else:
        entry = ActionableEntry(99.0, 101.0, 100.0, 100.0, 98.0, True)
        stop = StopLoss(103.0, 3.0, 3.0, ("structure",))
        target = TakeProfit("TP1", 94.0, 6.0, 2.0, ("liquidity",))
    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=direction,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=EntryStatus.READY_NOW if executable else EntryStatus.PULLBACK_PREFERRED,
        decision_time=NOW,
        candidate_id=candidate_id,
        confidence_score=70.0,
        entry=entry,
        stop_loss=stop,
        take_profits=(target,),
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


def test_selector_fills_current_and_nearby_slots_by_side() -> None:
    portfolio = portfolio_from_setups(
        (
            _setup("current-long", TradeDirection.LONG, executable=True),
            _setup("current-short", TradeDirection.SHORT, executable=True),
            _setup("nearby-long", TradeDirection.LONG, executable=False),
            _setup("nearby-short", TradeDirection.SHORT, executable=False),
        ),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert portfolio.current_long is not None
    assert portfolio.current_long.opportunity_id == "current-long"
    assert portfolio.current_short is not None
    assert portfolio.current_short.opportunity_id == "current-short"
    assert portfolio.nearby_long is not None
    assert portfolio.nearby_long.opportunity_id == "nearby-long"
    assert portfolio.nearby_short is not None
    assert portfolio.nearby_short.opportunity_id == "nearby-short"
    assert portfolio.follow_up_opportunities == ()


def test_analyze_retains_extra_distinct_setups_as_follow_ups() -> None:
    first = _setup("current-long", TradeDirection.LONG, executable=True)
    second = replace(
        first,
        candidate_id="second-current-long",
        entry=ActionableEntry(98.0, 100.0, 99.0, 100.0, 101.0, True),
        stop_loss=StopLoss(96.0, 3.0, 3.0, ("deeper_structure",)),
    )
    duplicate = replace(first)

    portfolio = portfolio_from_setups(
        (first, second, duplicate),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert portfolio.current_long is not None
    assert portfolio.current_long.opportunity_id == "current-long"
    assert tuple(item.opportunity_id for item in portfolio.follow_up_opportunities) == (
        "second-current-long",
    )
    assert portfolio.follow_up_opportunities[0].sequence_role is SequenceRole.FOLLOW_UP


def test_scan_uses_compact_fixed_slot_breadth() -> None:
    first = _setup("current-long", TradeDirection.LONG, executable=True)
    second = replace(first, candidate_id="second-current-long")
    nearby = _setup("nearby-long", TradeDirection.LONG, executable=False)
    extra_nearby = replace(nearby, candidate_id="second-nearby-long")

    portfolio = portfolio_from_setups(
        (first, second, nearby, extra_nearby),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )

    assert portfolio.current_long is not None
    assert portfolio.current_long.opportunity_id == "current-long"
    assert portfolio.nearby_long is not None
    assert portfolio.nearby_long.opportunity_id == "nearby-long"
    assert portfolio.follow_up_opportunities == ()


def test_selector_rejects_cross_symbol_setup() -> None:
    setup = replace(
        _setup("wrong-symbol", TradeDirection.LONG, executable=True),
        symbol="ETHUSDT",
    )

    try:
        portfolio_from_setups(
            (setup,),
            symbol="BTCUSDT",
            cmp=100.0,
            analysis_timestamp=NOW,
            analysis_mode=AnalysisMode.ANALYZE_FULL,
        )
    except ValueError as exc:
        assert str(exc) == "setup symbol must match portfolio symbol"
    else:
        raise AssertionError("expected cross-symbol setup rejection")
