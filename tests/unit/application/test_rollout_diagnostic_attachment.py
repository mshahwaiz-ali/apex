"""Tests for opt-in rollout diagnostic attachment."""

from __future__ import annotations

from datetime import UTC, datetime

from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoveryAssessment,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    ScanResult,
    StopLoss,
    SymbolAnalysis,
    TakeProfit,
)
from apex.application.enriched_public_output import (
    serialize_scan_result,
    serialize_symbol_analysis,
)
from apex.application.opportunity_portfolio import (
    AnalysisMode,
    portfolio_from_legacy_assessment,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


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


def _analysis() -> SymbolAnalysis:
    assessment = DiscoveryAssessment(
        symbol="BTCUSDT",
        decision_time=NOW,
        setup=_setup("selected-long"),
    )
    return SymbolAnalysis(
        symbol="BTCUSDT",
        generated_at=NOW,
        assessment=assessment,
        candidate_count=1,
        evaluated_timeframes=("5m", "15m"),
        regime_by_timeframe={"5m": "trend", "15m": "trend"},
        data_quality_by_timeframe={
            "5m": {"status": "complete"},
            "15m": {"status": "complete"},
        },
        opportunity_portfolio=portfolio_from_legacy_assessment(
            assessment,
            cmp=100.0,
            analysis_mode=AnalysisMode.ANALYZE_FULL,
        ),
    )


def test_symbol_default_payload_is_unchanged() -> None:
    analysis = _analysis()

    default_payload = serialize_symbol_analysis(analysis)
    explicit_default_payload = serialize_symbol_analysis(
        analysis,
        include_rollout_diagnostics=False,
    )

    assert default_payload == explicit_default_payload
    assert "rollout_comparison" not in default_payload


def test_symbol_opt_in_attaches_non_authoritative_comparison() -> None:
    payload = serialize_symbol_analysis(
        _analysis(),
        include_rollout_diagnostics=True,
    )

    diagnostic = payload["rollout_comparison"]
    assert isinstance(diagnostic, dict)
    assert diagnostic["authoritative"] is False
    assert diagnostic["symbol"] == "BTCUSDT"


def test_scan_default_payload_is_unchanged() -> None:
    scan = ScanResult(generated_at=NOW, analyses=(_analysis(),), failures={})

    default_payload = serialize_scan_result(scan)
    explicit_default_payload = serialize_scan_result(
        scan,
        include_rollout_diagnostics=False,
    )

    assert default_payload == explicit_default_payload
    assert "rollout_comparison_summary" not in default_payload
    results = default_payload["results"]
    assert isinstance(results, list)
    assert "rollout_comparison" not in results[0]


def test_scan_opt_in_attaches_result_and_summary_diagnostics() -> None:
    payload = serialize_scan_result(
        ScanResult(generated_at=NOW, analyses=(_analysis(),), failures={}),
        include_rollout_diagnostics=True,
    )

    results = payload["results"]
    assert isinstance(results, list)
    result_diagnostic = results[0]["rollout_comparison"]
    assert result_diagnostic["authoritative"] is False

    summary = payload["rollout_comparison_summary"]
    assert summary["authoritative"] is False
    assert summary["total_count"] == 1
    assert summary["difference_count"] == 1
    assert summary["regression_count"] == 0
