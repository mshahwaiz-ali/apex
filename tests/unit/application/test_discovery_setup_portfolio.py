from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

from apex.application import discovery_setup
from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    TakeProfit,
)
from apex.application.opportunity_portfolio import AnalysisMode
from apex.scoring.contracts import CandidateOutcome
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


def test_ranked_portfolio_keeps_all_accepted_candidates(monkeypatch) -> None:
    setups = {
        "current-long": _setup("current-long", TradeDirection.LONG, executable=True),
        "nearby-long": _setup("nearby-long", TradeDirection.LONG, executable=False),
        "current-short": _setup("current-short", TradeDirection.SHORT, executable=True),
    }
    accepted = SimpleNamespace(outcome=CandidateOutcome.ACCEPTED, key="current-long")
    warning = SimpleNamespace(
        outcome=CandidateOutcome.ACCEPTED_WITH_WARNING,
        key="nearby-long",
    )
    short = SimpleNamespace(outcome=CandidateOutcome.ACCEPTED, key="current-short")
    rejected = SimpleNamespace(outcome=CandidateOutcome.REJECTED_BELOW_THRESHOLD, key="rejected")
    selection = SimpleNamespace(
        symbol="BTCUSDT",
        decision_time=NOW,
        ranked_candidates=(accepted, warning, short, rejected),
    )

    monkeypatch.setattr(discovery_setup, "_build_setup", lambda item: setups[item.key])

    portfolio = discovery_setup.build_opportunity_portfolio(
        selection,
        cmp=100.0,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert portfolio.current_long is not None
    assert portfolio.current_long.opportunity_id == "current-long"
    assert portfolio.current_short is not None
    assert portfolio.current_short.opportunity_id == "current-short"
    assert portfolio.nearby_long is not None
    assert portfolio.nearby_long.opportunity_id == "nearby-long"
    assert portfolio.nearby_short is None
    assert portfolio.follow_up_opportunities == ()


def test_analyze_ranked_portfolio_preserves_follow_up_order(monkeypatch) -> None:
    first = _setup("first", TradeDirection.LONG, executable=True)
    second = replace(
        first,
        candidate_id="second",
        entry=ActionableEntry(98.0, 100.0, 99.0, 100.0, 101.0, True),
        stop_loss=StopLoss(96.0, 3.0, 3.0, ("deeper_structure",)),
    )
    third = replace(
        first,
        candidate_id="third",
        entry=ActionableEntry(97.0, 99.0, 98.0, 100.0, 100.0, False),
        stop_loss=StopLoss(95.0, 3.0, 3.0, ("deepest_structure",)),
        execution_allowed_now=False,
        entry_status=EntryStatus.PULLBACK_PREFERRED,
    )
    setups = {"first": first, "second": second, "third": third}
    items = tuple(
        SimpleNamespace(outcome=CandidateOutcome.ACCEPTED, key=key)
        for key in ("first", "second", "third")
    )
    selection = SimpleNamespace(
        symbol="BTCUSDT",
        decision_time=NOW,
        ranked_candidates=items,
    )

    monkeypatch.setattr(discovery_setup, "_build_setup", lambda item: setups[item.key])

    portfolio = discovery_setup.build_opportunity_portfolio(
        selection,
        cmp=100.0,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert portfolio.current_long is not None
    assert portfolio.current_long.opportunity_id == "first"
    assert portfolio.nearby_long is not None
    assert portfolio.nearby_long.opportunity_id == "third"
    assert tuple(item.opportunity_id for item in portfolio.follow_up_opportunities) == ("second",)
