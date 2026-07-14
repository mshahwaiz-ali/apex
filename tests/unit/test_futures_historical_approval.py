"""Integration coverage for typed historical evidence in futures plans."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from apex.application import build_futures_plan_result
from apex.backtesting import (
    EvidenceQuality,
    HistoricalEdgeValidationReason,
    HistoricalEdgeValidationResult,
    HistoricalEdgeValidationStatus,
)
from apex.domain import FuturesAccountInput, RiskMode
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
from apex.strategies import StrategyType, TradeDirection


def _account() -> FuturesAccountInput:
    return FuturesAccountInput(
        wallet_balance=10_000.0,
        risk_mode=RiskMode.STANDARD,
        maximum_account_loss_percentage=0.25,
    )


def _setup(*, confidence_score: float = 85.0) -> RiskApprovedSetup:
    return RiskApprovedSetup(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.TREND_PULLBACK,
        decision_time=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
        candidate_id="typed-evidence-fixture",
        confidence_score=confidence_score,
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
                rationale=("first structural target",),
                partial_close_pct=60.0,
            ),
            TakeProfit(
                label="TP2",
                price=106.0,
                reward=5.5,
                risk_reward=2.2,
                rationale=("second structural target",),
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
                rationale=("protect remaining position",),
            ),
        ),
    )


def _validated_evidence() -> HistoricalEdgeValidationResult:
    return HistoricalEdgeValidationResult(
        dimensions={
            "strategy": StrategyType.TREND_PULLBACK.value,
            "symbol": "BTCUSDT",
        },
        status=HistoricalEdgeValidationStatus.PASSED_VALIDATION,
        train_profile=None,
        validation_profile=None,
        test_profile=None,
        out_of_sample_sample_size=100,
        train_expectancy=1.0,
        validation_expectancy=0.7,
        test_expectancy=0.6,
        validation_profit_factor=1.5,
        test_profit_factor=1.4,
        validation_expectancy_degradation=0.3,
        test_expectancy_degradation=0.4,
        consistent_edge_direction=True,
        evidence_stable=True,
        promoted_evidence_quality=EvidenceQuality.VALIDATED_OUT_OF_SAMPLE,
        rejection_reasons=(),
        warnings=(HistoricalEdgeValidationReason.FORWARD_PAPER_VALIDATION_REQUIRED,),
    )


def test_futures_plan_serializes_typed_historical_evidence() -> None:
    result = build_futures_plan_result(
        _setup(),
        _account(),
        historical_edge_validation=_validated_evidence(),
    )

    assert result["status"] == "APPROVED"
    assert result["eligibility"] == "PAPER_ONLY"

    approval = result["strategy_approval"]
    assert isinstance(approval, dict)
    assert approval["eligibility"] == "PAPER_ONLY"

    evidence = approval["historical_evidence"]
    assert isinstance(evidence, dict)
    assert evidence["status"] == "PASSED_VALIDATION"
    assert evidence["out_of_sample_sample_size"] == 100
    assert evidence["evidence_stable"] is True
    assert evidence["promoted_evidence_quality"] == "VALIDATED_OUT_OF_SAMPLE"
    assert evidence["dimensions"] == {
        "strategy": StrategyType.TREND_PULLBACK.value,
        "symbol": "BTCUSDT",
    }

    reasons = approval["historical_evidence_reasons"]
    assert isinstance(reasons, list)
    assert [reason["code"] for reason in reasons] == [
        "OUT_OF_SAMPLE_EVIDENCE_VALIDATED",
        "FORWARD_PAPER_EVIDENCE_REQUIRED",
    ]


def test_boolean_and_typed_historical_evidence_are_mutually_exclusive() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "historical_evidence_available and historical_edge_validation "
            "cannot be supplied together"
        ),
    ):
        build_futures_plan_result(
            _setup(),
            _account(),
            historical_evidence_available=True,
            historical_edge_validation=_validated_evidence(),
        )


def test_typed_evidence_cannot_override_strategy_rejection() -> None:
    result = build_futures_plan_result(
        replace(_setup(), confidence_score=10.0),
        _account(),
        historical_edge_validation=_validated_evidence(),
    )

    assert result["status"] == "REJECTED"
    assert result["eligibility"] == "REJECTED"

    approval = result["strategy_approval"]
    assert isinstance(approval, dict)
    assert approval["historical_evidence"]["status"] == "PASSED_VALIDATION"
    assert approval["historical_evidence_reasons"] == []
    assert any("scored 10.00" in reason for reason in result["reasons"])


def test_legacy_boolean_path_remains_backward_compatible() -> None:
    result = build_futures_plan_result(
        _setup(),
        _account(),
        historical_evidence_available=True,
    )

    assert result["status"] == "APPROVED"
    assert result["eligibility"] == "PAPER_ONLY"

    approval = result["strategy_approval"]
    assert isinstance(approval, dict)
    assert approval["eligibility"] == "PAPER_ONLY"
    assert "historical_evidence" not in approval
