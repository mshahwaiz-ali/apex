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


def _setup(candidate_id: str = "current-long") -> DiscoverySetup:
    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=EntryStatus.READY_NOW,
        decision_time=NOW,
        candidate_id=candidate_id,
        confidence_score=78.0,
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


def _analysis_with_setup() -> SymbolAnalysis:
    assessment = DiscoveryAssessment(
        symbol="BTCUSDT",
        decision_time=NOW,
        setup=_setup(),
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
        methodology_gate={
            "status": "allowed",
            "allowed": True,
            "reasons": (),
        },
        opportunity_portfolio=portfolio_from_legacy_assessment(
            assessment,
            cmp=100.0,
            analysis_mode=AnalysisMode.ANALYZE_FULL,
        ),
    )


def _analysis_without_setup() -> SymbolAnalysis:
    return SymbolAnalysis(
        symbol="ETHUSDT",
        generated_at=NOW,
        assessment=DiscoveryAssessment(
            symbol="ETHUSDT",
            decision_time=NOW,
            setup=None,
            reasons=("mid-range conflicting structure", "no clear target room"),
        ),
        candidate_count=0,
        evaluated_timeframes=("5m", "15m"),
        regime_by_timeframe={"5m": "range", "15m": "mixed"},
        data_quality_by_timeframe={
            "5m": {"status": "complete"},
            "15m": {"status": "complete"},
        },
    )


def test_symbol_payload_serializes_canonical_opportunity_identity() -> None:
    payload = serialize_symbol_analysis(_analysis_with_setup())

    portfolio = payload["opportunity_portfolio"]
    assert portfolio["opportunity_count"] == 1

    opportunity = portfolio["opportunities"][0]
    assert opportunity["opportunity_id"] == "current-long"
    assert opportunity["category"] == "current"
    assert opportunity["sequence_role"] == "current"
    assert opportunity["direction"] == "long"
    assert opportunity["strategy"] == "breakout_continuation"
    assert opportunity["setup"]["candidate_id"] == "current-long"


def test_methodology_verdict_is_explicit_at_symbol_and_opportunity_level() -> None:
    payload = serialize_symbol_analysis(_analysis_with_setup())

    verdict = payload["methodology_verdict"]
    assert verdict == {
        "status": "allowed",
        "allowed": True,
        "authoritative": True,
        "source": "methodology_gate",
        "reasons": [],
        "notice": "Canonical symbol-level methodology-gate verdict.",
    }

    opportunity = payload["opportunity_portfolio"]["opportunities"][0]
    assert opportunity["methodology_verdict"] == verdict


def test_scan_counts_symbols_and_opportunities_separately() -> None:
    payload = serialize_scan_result(
        ScanResult(
            generated_at=NOW,
            analyses=(_analysis_with_setup(), _analysis_without_setup()),
            failures={},
        )
    )

    assert payload["total_symbol_count"] == 2
    assert payload["filtered_symbol_count"] == 2
    assert payload["displayed_symbol_count"] == 2
    assert payload["retained_opportunity_count"] == 1
    assert payload["displayed_opportunity_count"] == 1
    assert payload["current_opportunity_count"] == 1
    assert payload["nearby_opportunity_count"] == 0
    assert payload["follow_up_opportunity_count"] == 0
    assert payload["runner_opportunity_count"] == 0
    assert payload["long_candidate_count"] == 1
    assert payload["short_candidate_count"] == 0


def test_no_valid_setup_still_has_truthful_setup_plan() -> None:
    payload = serialize_symbol_analysis(_analysis_without_setup())

    plan = payload["setup_plan"]
    assert plan["status"] == "no_valid_setup_yet"
    assert plan["geometry_available"] is False
    assert plan["current_state"] == "mid-range conflicting structure"
    assert plan["long_trigger"] is None
    assert plan["short_trigger"] is None
    assert plan["invalidation"] is None
    assert plan["stop"] is None
    assert plan["targets"] == []
    assert plan["main_risk"] == "mid-range conflicting structure"
    assert plan["reasons"] == [
        "mid-range conflicting structure",
        "no clear target room",
    ]
    assert "fabricated" in plan["notice"]


def test_missing_methodology_gate_is_explicitly_non_authoritative() -> None:
    payload = serialize_symbol_analysis(_analysis_without_setup())

    assert payload["methodology_verdict"] == {
        "status": "unavailable",
        "allowed": None,
        "authoritative": False,
        "source": "methodology_gate",
        "reasons": [],
        "notice": "No canonical methodology-gate verdict was attached.",
    }
