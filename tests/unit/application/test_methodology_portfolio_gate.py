from __future__ import annotations

from datetime import UTC, datetime

from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoveryAssessment,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    TakeProfit,
)
from apex.application.methodology_portfolio_gate import (
    assessment_from_portfolio,
    filter_portfolio_by_methodology,
)
from apex.application.methodology_strategy_enforcement import (
    StrategyEnforcementAction,
    StrategyEnforcementDecision,
)
from apex.application.opportunity_portfolio import (
    AnalysisMode,
    SequenceRole,
    SymbolOpportunityPortfolio,
    TradeOpportunity,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _setup(
    candidate_id: str,
    *,
    direction: TradeDirection,
    strategy: StrategyType,
    executable: bool,
) -> DiscoverySetup:
    if direction is TradeDirection.LONG:
        entry = ActionableEntry(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=100.0 if executable else 97.0,
            maximum_chase_price=102.0,
            current_price_inside_zone=executable,
        )
        stop = StopLoss(
            price=96.0,
            distance=4.0,
            distance_pct=4.0,
            rationale=("below structure",),
        )
        target_price = 108.0
    else:
        entry = ActionableEntry(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=100.0 if executable else 103.0,
            maximum_chase_price=98.0,
            current_price_inside_zone=executable,
        )
        stop = StopLoss(
            price=104.0,
            distance=4.0,
            distance_pct=4.0,
            rationale=("above structure",),
        )
        target_price = 92.0

    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=direction,
        strategy=strategy,
        entry_status=EntryStatus.READY_NOW if executable else EntryStatus.WATCH_NEAR_ENTRY,
        decision_time=NOW,
        candidate_id=candidate_id,
        confidence_score=70.0,
        entry=entry,
        stop_loss=stop,
        take_profits=(
            TakeProfit(
                label="TP1",
                price=target_price,
                reward=8.0,
                risk_reward=2.0,
                rationale=("structural objective",),
            ),
        ),
        management_policies=(
            ManagementPolicy(
                kind=ManagementPolicyType.TIME_EXIT,
                trigger="setup expiry",
                action="cancel setup",
                rationale=("avoid stale exposure",),
            ),
        ),
        execution_allowed_now=executable,
    )


def _opportunity(setup: DiscoverySetup, role: SequenceRole) -> TradeOpportunity:
    return TradeOpportunity(
        opportunity_id=setup.candidate_id,
        setup=setup,
        sequence_role=role,
    )


def _decision(
    strategy: StrategyType,
    action: StrategyEnforcementAction,
) -> StrategyEnforcementDecision:
    return StrategyEnforcementDecision(
        strategy=strategy,
        action=action,
        reason_codes=(f"TEST_{action.value.upper()}",),
        reasons=(f"{strategy.value} is {action.value}",),
    )


def _portfolio() -> SymbolOpportunityPortfolio:
    current_long = _setup(
        "current-long",
        direction=TradeDirection.LONG,
        strategy=StrategyType.TREND_PULLBACK,
        executable=True,
    )
    current_short = _setup(
        "current-short",
        direction=TradeDirection.SHORT,
        strategy=StrategyType.FAILED_BREAKOUT_REVERSAL,
        executable=True,
    )
    nearby_long = _setup(
        "nearby-long",
        direction=TradeDirection.LONG,
        strategy=StrategyType.BREAKOUT_RETEST,
        executable=False,
    )
    return SymbolOpportunityPortfolio(
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
        current_long=_opportunity(current_long, SequenceRole.CURRENT),
        current_short=_opportunity(current_short, SequenceRole.CURRENT),
        nearby_long=_opportunity(nearby_long, SequenceRole.NEARBY),
    )


def _assessment(portfolio: SymbolOpportunityPortfolio) -> DiscoveryAssessment:
    assert portfolio.current_long is not None
    return DiscoveryAssessment(
        symbol=portfolio.symbol,
        decision_time=portfolio.analysis_timestamp,
        setup=portfolio.current_long.setup,
    )


def test_filter_removes_only_explicitly_suppressed_opportunity() -> None:
    portfolio = _portfolio()

    filtered, removed = filter_portfolio_by_methodology(
        portfolio,
        (
            _decision(StrategyType.TREND_PULLBACK, StrategyEnforcementAction.SUPPRESS),
            _decision(
                StrategyType.FAILED_BREAKOUT_REVERSAL,
                StrategyEnforcementAction.ALLOW,
            ),
            _decision(StrategyType.BREAKOUT_RETEST, StrategyEnforcementAction.DEFER),
        ),
    )

    assert filtered is not None
    assert filtered.current_long is None
    assert filtered.current_short is not None
    assert filtered.nearby_long is not None
    assert removed == ("current-long",)


def test_allowed_alternative_becomes_compatibility_selected_setup() -> None:
    portfolio = _portfolio()
    assessment = _assessment(portfolio)

    filtered, removed = filter_portfolio_by_methodology(
        portfolio,
        (
            _decision(StrategyType.TREND_PULLBACK, StrategyEnforcementAction.SUPPRESS),
            _decision(
                StrategyType.FAILED_BREAKOUT_REVERSAL,
                StrategyEnforcementAction.ALLOW,
            ),
            _decision(StrategyType.BREAKOUT_RETEST, StrategyEnforcementAction.ALLOW),
        ),
    )
    synchronized = assessment_from_portfolio(
        assessment,
        filtered,
        suppression_reasons=("suppressed methodology opportunity removed",),
    )

    assert removed == ("current-long",)
    assert synchronized.setup is not None
    assert synchronized.setup.candidate_id == "current-short"
    assert synchronized.developing_setup is not None
    assert synchronized.developing_setup.candidate_id == "nearby-long"


def test_nearby_setup_survives_when_all_current_opportunities_are_suppressed() -> None:
    portfolio = _portfolio()
    assessment = _assessment(portfolio)

    filtered, removed = filter_portfolio_by_methodology(
        portfolio,
        (
            _decision(StrategyType.TREND_PULLBACK, StrategyEnforcementAction.SUPPRESS),
            _decision(
                StrategyType.FAILED_BREAKOUT_REVERSAL,
                StrategyEnforcementAction.SUPPRESS,
            ),
            _decision(StrategyType.BREAKOUT_RETEST, StrategyEnforcementAction.ALLOW),
        ),
    )
    synchronized = assessment_from_portfolio(
        assessment,
        filtered,
        suppression_reasons=("current opportunities suppressed",),
    )

    assert filtered is not None
    assert removed == ("current-long", "current-short")
    assert synchronized.setup is None
    assert synchronized.developing_setup is not None
    assert synchronized.developing_setup.candidate_id == "nearby-long"


def test_all_suppressed_results_in_no_trade_assessment() -> None:
    portfolio = _portfolio()
    assessment = _assessment(portfolio)

    filtered, removed = filter_portfolio_by_methodology(
        portfolio,
        (
            _decision(StrategyType.TREND_PULLBACK, StrategyEnforcementAction.SUPPRESS),
            _decision(
                StrategyType.FAILED_BREAKOUT_REVERSAL,
                StrategyEnforcementAction.SUPPRESS,
            ),
            _decision(StrategyType.BREAKOUT_RETEST, StrategyEnforcementAction.SUPPRESS),
        ),
    )
    synchronized = assessment_from_portfolio(
        assessment,
        filtered,
        suppression_reasons=("all methodology opportunities suppressed",),
    )

    assert filtered is not None
    assert filtered.opportunities == ()
    assert removed == ("current-long", "current-short", "nearby-long")
    assert synchronized.setup is None
    assert synchronized.developing_setup is None
    assert synchronized.reasons == ("all methodology opportunities suppressed",)
