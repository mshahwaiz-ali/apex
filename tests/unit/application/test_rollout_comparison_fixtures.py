"""Deterministic fixture integration for rollout comparison diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime

from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoveryAssessment,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    SymbolAnalysis,
    TakeProfit,
)
from apex.application.opportunity_portfolio import (
    AnalysisMode,
    opportunity_portfolio_payload,
    portfolio_from_legacy_assessment,
)
from apex.application.public_output import serialize_symbol_analysis
from apex.application.rollout_comparison import (
    AnalysisComparisonReport,
    compare_analysis_outputs,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


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


def _analysis(assessment: DiscoveryAssessment) -> SymbolAnalysis:
    portfolio = portfolio_from_legacy_assessment(
        assessment,
        cmp=100.0,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )
    return SymbolAnalysis(
        symbol=assessment.symbol,
        generated_at=NOW,
        assessment=assessment,
        candidate_count=sum(
            item is not None for item in (assessment.setup, assessment.developing_setup)
        ),
        evaluated_timeframes=("5m", "15m"),
        regime_by_timeframe={"5m": "trend", "15m": "trend"},
        data_quality_by_timeframe={
            "5m": {"status": "complete"},
            "15m": {"status": "complete"},
        },
        opportunity_portfolio=portfolio,
    )


def _compare(analysis: SymbolAnalysis) -> AnalysisComparisonReport:
    legacy_payload = serialize_symbol_analysis(analysis)
    assert analysis.opportunity_portfolio is not None
    new_payload = {
        "symbol": analysis.symbol,
        "opportunity_portfolio": opportunity_portfolio_payload(analysis.opportunity_portfolio),
        "rejection_reasons": list(analysis.assessment.reasons),
    }
    return compare_analysis_outputs(legacy_payload, new_payload)


def test_selected_fixture_matches_primary_portfolio_geometry() -> None:
    selected = _setup("selected-long", TradeDirection.LONG, executable=True)
    analysis = _analysis(
        DiscoveryAssessment(
            symbol="BTCUSDT",
            decision_time=NOW,
            setup=selected,
        )
    )

    report = _compare(analysis)

    fields = {difference.field for difference in report.differences}
    assert report.legacy_opportunity_count == 1
    assert report.new_opportunity_count == 1
    assert "selected_strategy" not in fields
    assert "direction" not in fields
    assert "entry_zone" not in fields
    assert "stop" not in fields
    assert "targets" not in fields
    assert fields == {"actionability_state", "confidence", "ranking_score"}


def test_developing_fixture_preserves_nearby_geometry() -> None:
    developing = _setup(
        "developing-short",
        TradeDirection.SHORT,
        executable=False,
    )
    analysis = _analysis(
        DiscoveryAssessment(
            symbol="BTCUSDT",
            decision_time=NOW,
            setup=None,
            reasons=("no immediate setup",),
            developing_setup=developing,
        )
    )

    report = _compare(analysis)

    fields = {difference.field for difference in report.differences}
    assert report.legacy_opportunity_count == 1
    assert report.new_opportunity_count == 1
    assert "selected_strategy" not in fields
    assert "direction" not in fields
    assert "entry_zone" not in fields
    assert "stop" not in fields
    assert "targets" not in fields
    assert fields == {"actionability_state", "confidence", "ranking_score"}


def test_selected_and_developing_fixture_exposes_count_difference_only() -> None:
    selected = _setup("selected-long", TradeDirection.LONG, executable=True)
    developing = _setup(
        "developing-short",
        TradeDirection.SHORT,
        executable=False,
    )
    analysis = _analysis(
        DiscoveryAssessment(
            symbol="BTCUSDT",
            decision_time=NOW,
            setup=selected,
            developing_setup=developing,
        )
    )

    report = _compare(analysis)

    differences = {difference.field: difference for difference in report.differences}
    assert differences["opportunity_count"].legacy == 1
    assert differences["opportunity_count"].new == 2
    for field in ("selected_strategy", "direction", "entry_zone", "stop", "targets"):
        assert field not in differences
    assert set(differences) == {
        "opportunity_count",
        "actionability_state",
        "confidence",
        "ranking_score",
    }


def test_no_trade_fixture_remains_explicit_and_non_authoritative() -> None:
    analysis = _analysis(
        DiscoveryAssessment(
            symbol="BTCUSDT",
            decision_time=NOW,
            setup=None,
            reasons=("fixture rejection",),
        )
    )

    report = _compare(analysis)

    assert report.legacy_opportunity_count == 0
    assert report.new_opportunity_count == 0
    assert report.interpretation.startswith("diagnostic comparison only")
