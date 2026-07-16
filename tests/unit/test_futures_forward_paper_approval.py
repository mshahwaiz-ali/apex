"""Forward-paper eligibility integration for futures plans."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.application import build_futures_plan_result
from apex.backtesting import (
    EvidenceQuality,
    HistoricalEdgeValidationResult,
    HistoricalEdgeValidationStatus,
)
from apex.domain import FuturesAccountInput, RiskMode, ScannerMode
from apex.paper_trading import (
    ForwardPaperEdgeProfile,
    ForwardPaperValidationReason,
    ForwardPaperValidationResult,
    ForwardPaperValidationStatus,
)
from apex.risk.contracts import (
    ActionableEntry,
    LeverageRange,
    ManagementPolicy,
    ManagementPolicyType,
    PositionSize,
    RiskApprovedSetup,
    StopLoss,
    TakeProfit,
)
from apex.scoring import SetupSegmentContext
from apex.strategies import StrategyType, TradeDirection

DIMENSIONS = {
    "strategy": StrategyType.TREND_PULLBACK.value,
    "symbol": "BTCUSDT",
    "direction": TradeDirection.LONG.value,
    "risk_mode": RiskMode.STANDARD.value,
    "scanner_type": "normal",
    "market_regime": "trend",
    "score_band": "85_89",
}


SEGMENT_CONTEXT = SetupSegmentContext(
    scanner_type=ScannerMode.NORMAL,
    market_regime="trend",
)


def _account(risk_mode: RiskMode = RiskMode.STANDARD) -> FuturesAccountInput:
    return FuturesAccountInput(
        wallet_balance=10_000.0,
        risk_mode=risk_mode,
        maximum_account_loss_percentage=0.25,
    )


def _setup() -> RiskApprovedSetup:
    return RiskApprovedSetup(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.TREND_PULLBACK,
        decision_time=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
        candidate_id="forward-paper-fixture",
        confidence_score=85.0,
        entry=ActionableEntry(
            lower=100.0,
            upper=101.0,
            preferred=100.5,
            current_price=100.6,
            maximum_chase_price=101.5,
            current_price_inside_zone=True,
        ),
        stop_loss=StopLoss(
            price=98.0,
            distance=2.5,
            distance_pct=2.487562189054726,
            rationale=("structure invalidation",),
            quality_score=0.8,
        ),
        take_profits=(
            TakeProfit(
                label="TP1",
                price=103.0,
                reward=2.5,
                risk_reward=1.0,
                rationale=("first target",),
                partial_close_pct=60.0,
            ),
            TakeProfit(
                label="TP2",
                price=106.0,
                reward=5.5,
                risk_reward=2.2,
                rationale=("second target",),
                partial_close_pct=40.0,
            ),
        ),
        position_size=PositionSize(
            risk_amount=25.0,
            quantity=10.0,
            notional_value=1005.0,
            account_risk_pct=0.25,
            required_leverage=2.0,
        ),
        leverage=LeverageRange(
            minimum=1.0,
            maximum=5.0,
            modeled_maximum=10.0,
            liquidation_price_at_maximum=50.0,
            stop_to_liquidation_buffer_pct=48.0,
        ),
        management_policies=(
            ManagementPolicy(
                kind=ManagementPolicyType.BREAKEVEN,
                trigger="TP1 reached",
                action="move stop to breakeven",
                rationale=("protect remainder",),
            ),
        ),
    )


def _historical() -> HistoricalEdgeValidationResult:
    return HistoricalEdgeValidationResult(
        dimensions=DIMENSIONS,
        status=HistoricalEdgeValidationStatus.PASSED_VALIDATION,
        train_profile=None,
        validation_profile=None,
        test_profile=None,
        out_of_sample_sample_size=150,
        train_expectancy=0.8,
        validation_expectancy=0.6,
        test_expectancy=0.5,
        validation_profit_factor=1.5,
        test_profit_factor=1.4,
        validation_expectancy_degradation=0.25,
        test_expectancy_degradation=0.375,
        consistent_edge_direction=True,
        evidence_stable=True,
        promoted_evidence_quality=EvidenceQuality.VALIDATED_OUT_OF_SAMPLE,
        rejection_reasons=(),
        warnings=(),
    )


def _forward(
    historical: HistoricalEdgeValidationResult,
    *,
    dimensions: dict[str, str] | None = None,
    status: ForwardPaperValidationStatus = (ForwardPaperValidationStatus.PASSED_VALIDATION),
) -> ForwardPaperValidationResult:
    resolved_dimensions = dimensions or DIMENSIONS
    passed = status is ForwardPaperValidationStatus.PASSED_VALIDATION

    return ForwardPaperValidationResult(
        dimensions=resolved_dimensions,
        status=status,
        historical_validation=historical,
        forward_profile=ForwardPaperEdgeProfile(
            dimensions=resolved_dimensions,
            sample_size=120,
            win_rate=0.56,
            expectancy=0.35,
            profit_factor=1.3,
            maximum_drawdown_r=6.0,
        ),
        expectancy_degradation_from_test=0.30,
        consistent_edge_direction=True,
        evidence_stable=passed,
        promoted_evidence_quality=(EvidenceQuality.VALIDATED_FORWARD_PAPER if passed else None),
        rejection_reasons=(
            () if passed else (ForwardPaperValidationReason.FORWARD_EXPECTANCY_NOT_POSITIVE,)
        ),
        warnings=(
            (ForwardPaperValidationReason.PRODUCTION_ELIGIBILITY_NOT_INCLUDED,) if passed else ()
        ),
    )


def test_exact_standard_segment_can_become_funded_eligible() -> None:
    historical = _historical()
    result = build_futures_plan_result(
        _setup(),
        _account(),
        historical_edge_validation=historical,
        forward_paper_validation=_forward(historical),
        setup_segment_context=SEGMENT_CONTEXT,
    )

    assert result["status"] == "APPROVED"
    assert result["eligibility"] == "FUNDED_ELIGIBLE"

    approval = result["strategy_approval"]
    assert isinstance(approval, dict)
    assert approval["effective_eligibility"] == "FUNDED_ELIGIBLE"
    assert approval["historical_evidence"]["status"] == "PASSED_VALIDATION"
    assert approval["forward_paper_evidence"]["status"] == "PASSED_VALIDATION"


def test_legacy_scanner_dimension_does_not_cause_segment_mismatch() -> None:
    historical = _historical()
    legacy_forward_dimensions = {**DIMENSIONS, "scanner_type": "gainers"}

    result = build_futures_plan_result(
        _setup(),
        _account(),
        historical_edge_validation=historical,
        forward_paper_validation=_forward(
            historical,
            dimensions=legacy_forward_dimensions,
        ),
        setup_segment_context=SEGMENT_CONTEXT,
    )

    assert result["status"] == "APPROVED"
    assert result["eligibility"] == "FUNDED_ELIGIBLE"


def test_mismatched_forward_segment_remains_paper_only() -> None:
    historical = _historical()
    mismatched = {**DIMENSIONS, "market_regime": "range"}

    result = build_futures_plan_result(
        _setup(),
        _account(),
        historical_edge_validation=historical,
        forward_paper_validation=_forward(
            historical,
            dimensions=mismatched,
        ),
        setup_segment_context=SEGMENT_CONTEXT,
    )

    assert result["status"] == "APPROVED"
    assert result["eligibility"] == "PAPER_ONLY"

    approval = result["strategy_approval"]
    assert isinstance(approval, dict)
    reasons = approval["forward_paper_evidence_reasons"]
    assert isinstance(reasons, list)
    assert [reason["code"] for reason in reasons] == ["FORWARD_PAPER_SEGMENT_MISMATCH"]


def test_failed_forward_validation_remains_paper_only() -> None:
    historical = _historical()
    result = build_futures_plan_result(
        _setup(),
        _account(),
        historical_edge_validation=historical,
        forward_paper_validation=_forward(
            historical,
            status=ForwardPaperValidationStatus.FAILED_VALIDATION,
        ),
        setup_segment_context=SEGMENT_CONTEXT,
    )

    assert result["status"] == "APPROVED"
    assert result["eligibility"] == "PAPER_ONLY"


def test_aggressive_mode_cannot_become_funded_eligible() -> None:
    historical = _historical()
    result = build_futures_plan_result(
        _setup(),
        _account(RiskMode.AGGRESSIVE),
        historical_edge_validation=historical,
        forward_paper_validation=_forward(historical),
        setup_segment_context=SEGMENT_CONTEXT,
    )

    assert result["status"] == "APPROVED"
    assert result["eligibility"] == "PAPER_ONLY"


def test_forward_evidence_requires_historical_evidence() -> None:
    historical = _historical()

    with pytest.raises(
        ValueError,
        match="forward_paper_validation requires historical_edge_validation",
    ):
        build_futures_plan_result(
            _setup(),
            _account(),
            forward_paper_validation=_forward(historical),
            setup_segment_context=SEGMENT_CONTEXT,
        )
