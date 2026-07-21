from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoveryAssessment,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    TakeProfit,
)
from apex.application.opportunity_portfolio import (
    AnalysisMode,
    PortfolioDecisionState,
    SequenceRole,
    SymbolOpportunityPortfolio,
    TradeOpportunity,
    portfolio_from_legacy_assessment,
)
from apex.strategies.contracts import EntryMode, TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _setup(
    candidate_id: str,
    direction: TradeDirection,
    *,
    executable: bool,
) -> DiscoverySetup:
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


def test_legacy_adapter_preserves_current_and_developing_setups() -> None:
    selected = _setup("selected", TradeDirection.LONG, executable=True)
    developing = _setup("developing", TradeDirection.SHORT, executable=False)
    assessment = DiscoveryAssessment(
        symbol="BTCUSDT",
        decision_time=NOW,
        setup=selected,
        developing_setup=developing,
    )

    portfolio = portfolio_from_legacy_assessment(
        assessment,
        cmp=100.0,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert portfolio.current_long is not None
    assert portfolio.current_long.opportunity_id == "selected"
    assert portfolio.nearby_short is not None
    assert portfolio.nearby_short.opportunity_id == "developing"
    assert tuple(item.opportunity_id for item in portfolio.opportunities) == (
        "selected",
        "developing",
    )


def test_portfolio_rejects_duplicate_slot_identity() -> None:
    setup = _setup("same", TradeDirection.LONG, executable=True)
    current = TradeOpportunity("same", setup, SequenceRole.CURRENT)
    follow_up = TradeOpportunity(
        "same",
        replace(setup, execution_allowed_now=False),
        SequenceRole.FOLLOW_UP,
    )

    with pytest.raises(ValueError, match="duplicate opportunities"):
        SymbolOpportunityPortfolio(
            symbol="BTCUSDT",
            cmp=100.0,
            analysis_timestamp=NOW,
            analysis_mode=AnalysisMode.ANALYZE_FULL,
            current_long=current,
            follow_up_opportunities=(follow_up,),
        )


def test_current_opportunity_requires_immediate_execution() -> None:
    setup = _setup("nearby", TradeDirection.LONG, executable=False)

    with pytest.raises(ValueError, match="authorize execution now"):
        TradeOpportunity("nearby", setup, SequenceRole.CURRENT)


def test_portfolio_public_decision_prefers_current_over_nearby() -> None:
    current_setup = _setup("current-long", TradeDirection.LONG, executable=True)
    nearby_setup = _setup("nearby-short", TradeDirection.SHORT, executable=False)
    portfolio = SymbolOpportunityPortfolio(
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
        current_long=TradeOpportunity(
            current_setup.candidate_id,
            current_setup,
            SequenceRole.CURRENT,
        ),
        nearby_short=TradeOpportunity(
            nearby_setup.candidate_id,
            nearby_setup,
            SequenceRole.NEARBY,
        ),
    )

    assert portfolio.public_decision is PortfolioDecisionState.ACTIONABLE_AT_CMP
    assert portfolio.primary_opportunity is not None
    assert portfolio.primary_opportunity.opportunity_id == "current-long"
    assert portfolio.has_direction(TradeDirection.LONG)
    assert portfolio.has_direction(TradeDirection.SHORT)
    assert portfolio.all_opportunities == portfolio.opportunities


def test_confirmation_pending_current_opportunity_is_not_actionable_at_cmp() -> None:
    setup = replace(
        _setup("confirmation-long", TradeDirection.LONG, executable=False),
        entry_status=EntryStatus.WATCH_NEAR_ENTRY,
        entry_mode=EntryMode.RETEST,
        confirmation_required=True,
        confirmation_complete=False,
        provisional=True,
        canonical_actionability=True,
    )
    portfolio = SymbolOpportunityPortfolio(
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
        current_long=TradeOpportunity(
            setup.candidate_id,
            setup,
            SequenceRole.CURRENT,
        ),
    )

    assert portfolio.current_opportunities
    assert portfolio.execution_ready_opportunities == ()
    assert portfolio.public_decision is PortfolioDecisionState.CONFIRMATION_AT_CMP


def test_portfolio_public_decision_preserves_nearby_setup_without_current_trade() -> None:
    nearby_setup = _setup("nearby-long", TradeDirection.LONG, executable=False)
    portfolio = SymbolOpportunityPortfolio(
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
        nearby_long=TradeOpportunity(
            nearby_setup.candidate_id,
            nearby_setup,
            SequenceRole.NEARBY,
        ),
    )

    assert portfolio.public_decision is PortfolioDecisionState.NEARBY_SETUP_AVAILABLE
    assert portfolio.primary_opportunity is not None
    assert portfolio.primary_opportunity.opportunity_id == "nearby-long"


def test_empty_portfolio_has_no_valid_setup_decision() -> None:
    portfolio = SymbolOpportunityPortfolio(
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert portfolio.public_decision is PortfolioDecisionState.NO_VALID_SETUP
    assert portfolio.primary_opportunity is None
