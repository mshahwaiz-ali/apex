from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

from apex.application.analysis import ScanResult, SymbolAnalysis
from apex.application.paper_pipeline_diagnostics import build_futures_pipeline_diagnostics
from apex.application.phase6_pipeline_diagnostics import (
    build_phase6_diagnostic_summary,
    phase6_analysis_payload,
)
from apex.domain import MarketCategory
from apex.risk import (
    ActionableEntry,
    LeverageRange,
    ManagementPolicy,
    ManagementPolicyType,
    PositionSize,
    RiskApprovedSetup,
    RiskAssessment,
    RiskDecision,
    RiskRejectionCode,
    StopLoss,
    StopQualityBand,
    TakeProfit,
)
from apex.strategies import StrategyType, TradeDirection

NOW = datetime(2026, 7, 16, tzinfo=UTC)


def _approved_analysis() -> SymbolAnalysis:
    setup = RiskApprovedSetup(
        symbol="BTC/USDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.TREND_PULLBACK,
        decision_time=NOW,
        candidate_id="candidate-1",
        confidence_score=81.0,
        entry=ActionableEntry(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=100.5,
            maximum_chase_price=102.0,
            current_price_inside_zone=True,
        ),
        stop_loss=StopLoss(
            price=97.0,
            distance=3.0,
            distance_pct=3.0,
            rationale=("structure",),
            quality_score=0.8,
            quality_band=StopQualityBand.STRONG,
        ),
        take_profits=(
            TakeProfit(
                label="TP1",
                price=105.0,
                reward=5.0,
                risk_reward=1.67,
                rationale=("first target",),
                partial_close_pct=50.0,
            ),
            TakeProfit(
                label="TP2",
                price=110.0,
                reward=10.0,
                risk_reward=3.33,
                rationale=("runner target",),
                partial_close_pct=50.0,
            ),
        ),
        position_size=PositionSize(
            risk_amount=10.0,
            quantity=3.0,
            notional_value=300.0,
            account_risk_pct=1.0,
            required_leverage=12.0,
        ),
        leverage=LeverageRange(
            minimum=5.0,
            maximum=15.0,
            modeled_maximum=20.0,
            liquidation_price_at_maximum=90.0,
            stop_to_liquidation_buffer_pct=7.0,
        ),
        management_policies=(
            ManagementPolicy(
                kind=ManagementPolicyType.BREAKEVEN,
                trigger="after TP1",
                action="move stop to entry",
                rationale=("protect capital",),
            ),
        ),
    )
    assessment = RiskAssessment(
        symbol="BTC/USDT",
        decision_time=NOW,
        decision=RiskDecision.APPROVED,
        setup=setup,
        rejection_codes=(),
        reasons=(),
        configuration_id="risk-test",
    )
    return cast(
        SymbolAnalysis,
        SimpleNamespace(
            symbol="BTC/USDT",
            scanner_type=MarketCategory.NORMAL_MARKET,
            assessment=assessment,
            candidate_count=1,
            strategy_routing={},
            phase5_diagnostics={
                "selected_candidate_id": "candidate-1",
                "candidates": [
                    {
                        "candidate_id": "candidate-1",
                        "strategy": "trend_pullback",
                    }
                ],
            },
            risk_rejection_diagnostics=(),
        ),
    )


def _rejected_analysis() -> SymbolAnalysis:
    assessment = RiskAssessment(
        symbol="ETH/USDT",
        decision_time=NOW,
        decision=RiskDecision.REJECTED,
        setup=None,
        rejection_codes=(
            RiskRejectionCode.STOP_TOO_TIGHT,
            RiskRejectionCode.LEVERAGE_UNSAFE,
        ),
        reasons=("stop inside noise", "required leverage exceeds safe maximum"),
        configuration_id="risk-test",
    )
    return cast(
        SymbolAnalysis,
        SimpleNamespace(
            symbol="ETH/USDT",
            scanner_type=MarketCategory.GAINER,
            assessment=assessment,
            candidate_count=1,
            strategy_routing={},
            phase5_diagnostics={
                "selected_candidate_id": "candidate-2",
                "candidates": [
                    {
                        "candidate_id": "candidate-2",
                        "strategy": "breakout_continuation",
                    }
                ],
            },
            risk_rejection_diagnostics=({"rejection_codes": ["stop_too_tight"]},),
        ),
    )


def test_phase6_summary_aggregates_approvals_rejections_and_geometry() -> None:
    payload = build_phase6_diagnostic_summary(
        (_approved_analysis(), _rejected_analysis())
    ).to_payload()

    assert payload["decision_funnel"] == {
        "observed": 2,
        "approved": 1,
        "rejected": 1,
    }
    assert payload["rejection_code_counts"] == {
        "leverage_unsafe": 1,
        "stop_too_tight": 1,
    }
    assert payload["rejection_counts_by_scanner_category"] == {
        "GAINER": {"leverage_unsafe": 1, "stop_too_tight": 1}
    }
    assert payload["rejection_counts_by_strategy"] == {
        "breakout_continuation": {
            "leverage_unsafe": 1,
            "stop_too_tight": 1,
        }
    }
    assert payload["approved_counts_by_strategy"] == {"trend_pullback": 1}
    assert payload["approved_counts_by_direction"] == {"long": 1}
    assert payload["stop_quality_band_counts"] == {"strong": 1}
    assert payload["leverage_band_counts"] == {
        "1_5x": 0,
        "5_10x": 0,
        "10_20x": 1,
        "above_20x": 0,
    }
    assert payload["target_count_distribution"] == {"2": 1}
    assert payload["averages"] == {
        "required_leverage": 12.0,
        "account_risk_pct": 1.0,
        "stop_distance_pct": 3.0,
    }


def test_phase6_analysis_payload_preserves_structured_details() -> None:
    approved = phase6_analysis_payload(_approved_analysis())
    rejected = phase6_analysis_payload(_rejected_analysis())

    assert approved["decision"] == "approved"
    assert approved["approved_setup"]["candidate_id"] == "candidate-1"
    assert approved["approved_setup"]["leverage"]["maximum"] == 15.0
    assert approved["approved_setup"]["take_profit_count"] == 2
    assert rejected["decision"] == "rejected"
    assert rejected["approved_setup"] is None
    assert rejected["selected_strategy"] == "breakout_continuation"
    assert rejected["rejection_codes"] == ["stop_too_tight", "leverage_unsafe"]


def test_pipeline_payload_includes_phase6_summary_and_distinct_paths() -> None:
    scan = cast(
        ScanResult,
        SimpleNamespace(
            analyses=(_approved_analysis(), _rejected_analysis()),
            failures={},
        ),
    )

    payload = build_futures_pipeline_diagnostics(scan)

    assert payload["phase6_summary"]["decision_funnel"]["approved"] == 1
    assert set(payload["phase6_analyses"]) == {
        "BTC/USDT:NORMAL_MARKET",
        "ETH/USDT:GAINER",
    }
