from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from apex.application.discovery_analysis import serialize_symbol_analysis
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
    SequenceRole,
    SymbolOpportunityPortfolio,
    TradeOpportunity,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _setup(candidate_id: str, *, executable: bool) -> DiscoverySetup:
    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.BREAKOUT_RETEST,
        entry_status=(EntryStatus.READY_NOW if executable else EntryStatus.PULLBACK_PREFERRED),
        decision_time=NOW,
        candidate_id=candidate_id,
        confidence_score=72.0,
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


def _analysis(
    *,
    legacy_setup: DiscoverySetup | None,
    portfolio: SymbolOpportunityPortfolio,
) -> SimpleNamespace:
    return SimpleNamespace(
        symbol="BTCUSDT",
        generated_at=NOW,
        assessment=DiscoveryAssessment(
            symbol="BTCUSDT",
            decision_time=NOW,
            setup=legacy_setup,
            developing_setup=None,
            reasons=() if legacy_setup is not None else ("legacy reason",),
        ),
        candidate_count=1,
        evaluated_timeframes=("5m",),
        regime_by_timeframe={},
        data_quality_by_timeframe={},
        strategy_routing={},
        phase5_diagnostics={},
        market_intelligence={},
        historical_edge={},
        candidate_ranking=None,
        methodology=None,
        opportunity_portfolio=portfolio,
    )


def test_nearby_portfolio_setup_does_not_serialize_as_no_trade() -> None:
    nearby = _setup("nearby", executable=False)
    portfolio = SymbolOpportunityPortfolio(
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
        nearby_long=TradeOpportunity("nearby", nearby, SequenceRole.NEARBY),
    )

    payload = serialize_symbol_analysis(_analysis(legacy_setup=None, portfolio=portfolio))

    assert payload["decision"] == "LONG"
    assert payload["portfolio_decision"] == "nearby_setup_available"
    assert payload["setup"] is None
    assert payload["developing_setup"]["candidate_id"] == "nearby"
    assert payload["legacy_decision"] == "NO_TRADE"
    assert payload["legacy_assessment"]["setup"] is None


def test_current_portfolio_setup_is_canonical_over_legacy_setup() -> None:
    legacy = _setup("legacy", executable=False)
    current = _setup("current", executable=True)
    portfolio = SymbolOpportunityPortfolio(
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
        current_long=TradeOpportunity("current", current, SequenceRole.CURRENT),
    )

    payload = serialize_symbol_analysis(_analysis(legacy_setup=legacy, portfolio=portfolio))

    assert payload["setup"]["candidate_id"] == "current"
    assert payload["developing_setup"] is None
    assert payload["legacy_assessment"]["setup"]["candidate_id"] == "legacy"
    assert payload["portfolio_decision"] == "actionable_at_cmp"
