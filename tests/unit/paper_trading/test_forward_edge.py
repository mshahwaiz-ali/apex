"""Tests for V1.6 forward-paper evidence evaluation and promotion."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.backtesting import (
    BacktestSignal,
    EvidenceQuality,
    HistoricalEdgeValidationReason,
    HistoricalEdgeValidationResult,
    HistoricalEdgeValidationStatus,
)
from apex.paper_trading import PaperTrade, PaperTradeState
from apex.paper_trading.forward_edge_contracts import (
    ForwardPaperValidationPolicy,
    ForwardPaperValidationReason,
    ForwardPaperValidationStatus,
)
from apex.paper_trading.forward_edge_evaluation import evaluate_forward_paper_edge
from apex.strategies import StrategyType, TradeDirection


def _historical(
    *,
    status: HistoricalEdgeValidationStatus = HistoricalEdgeValidationStatus.PASSED_VALIDATION,
    test_expectancy: float = 0.5,
) -> HistoricalEdgeValidationResult:
    passed = status is HistoricalEdgeValidationStatus.PASSED_VALIDATION
    return HistoricalEdgeValidationResult(
        dimensions={"strategy": StrategyType.TREND_PULLBACK.value, "symbol": "BTCUSDT"},
        status=status,
        train_profile=None,
        validation_profile=None,
        test_profile=None,
        out_of_sample_sample_size=100,
        train_expectancy=0.8,
        validation_expectancy=0.6,
        test_expectancy=test_expectancy,
        validation_profit_factor=1.4,
        test_profit_factor=1.3,
        validation_expectancy_degradation=0.25,
        test_expectancy_degradation=0.375,
        consistent_edge_direction=passed,
        evidence_stable=passed,
        promoted_evidence_quality=(EvidenceQuality.VALIDATED_OUT_OF_SAMPLE if passed else None),
        rejection_reasons=()
        if passed
        else (HistoricalEdgeValidationReason.TEST_EXPECTANCY_NOT_POSITIVE,),
        warnings=(HistoricalEdgeValidationReason.FORWARD_PAPER_VALIDATION_REQUIRED,)
        if passed
        else (),
    )


def _trade(index: int, realized_r: float, *, state: PaperTradeState | None = None) -> PaperTrade:
    generated_at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=index)
    resolved_state = state or (
        PaperTradeState.TARGET_HIT if realized_r > 0.0 else PaperTradeState.STOPPED
    )
    entered = resolved_state in {PaperTradeState.TARGET_HIT, PaperTradeState.STOPPED}
    signal = BacktestSignal(
        symbol="BTCUSDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=generated_at,
        entry_price=100.0,
        stop_price=99.0,
        target_price=102.0,
        quantity=1.0,
        risk_amount=1.0,
        confidence_score=80.0,
    )
    return PaperTrade(
        trade_id=f"paper-{index}",
        signal=signal,
        state=resolved_state,
        created_at=generated_at,
        updated_at=generated_at + timedelta(minutes=30),
        analysis_payload={"active_risk_mode": "STANDARD"},
        entry_time=generated_at + timedelta(minutes=5) if entered else None,
        entry_price=100.0 if entered else None,
        exit_time=generated_at + timedelta(minutes=30)
        if resolved_state
        in {PaperTradeState.TARGET_HIT, PaperTradeState.STOPPED, PaperTradeState.EXPIRED}
        else None,
        exit_price=102.0 if realized_r > 0.0 and entered else 99.0 if entered else None,
        net_pnl=realized_r if entered else 0.0,
        realized_r_multiple=realized_r if entered else 0.0,
    )


def _policy() -> ForwardPaperValidationPolicy:
    return ForwardPaperValidationPolicy(minimum_closed_trades=4)


def test_forward_paper_evidence_promotes_only_to_validated_forward_paper() -> None:
    trades = tuple(_trade(index, value) for index, value in enumerate((1.0, 1.0, -0.5, 0.5)))

    result = evaluate_forward_paper_edge(_historical(), trades, policy=_policy())

    assert result.status is ForwardPaperValidationStatus.PASSED_VALIDATION
    assert result.promoted_evidence_quality is EvidenceQuality.VALIDATED_FORWARD_PAPER
    assert result.forward_profile is not None
    assert result.forward_profile.sample_size == 4
    assert result.forward_profile.expectancy == pytest.approx(0.5)
    assert result.warnings == (ForwardPaperValidationReason.PRODUCTION_ELIGIBILITY_NOT_INCLUDED,)


def test_insufficient_sample_is_not_promoted() -> None:
    result = evaluate_forward_paper_edge(
        _historical(),
        (_trade(0, 1.0), _trade(1, -0.5)),
        policy=_policy(),
    )

    assert result.status is ForwardPaperValidationStatus.INSUFFICIENT_SAMPLE
    assert ForwardPaperValidationReason.FORWARD_SAMPLE_INSUFFICIENT in result.rejection_reasons
    assert result.promoted_evidence_quality is None


def test_failed_historical_validation_blocks_forward_promotion() -> None:
    result = evaluate_forward_paper_edge(
        _historical(status=HistoricalEdgeValidationStatus.FAILED_VALIDATION),
        tuple(_trade(index, 1.0) for index in range(4)),
        policy=_policy(),
    )

    assert result.status is ForwardPaperValidationStatus.INSUFFICIENT_SAMPLE
    assert (
        ForwardPaperValidationReason.HISTORICAL_OUT_OF_SAMPLE_REQUIRED in result.rejection_reasons
    )


def test_negative_forward_expectancy_fails() -> None:
    trades = tuple(_trade(index, value) for index, value in enumerate((-1.0, -1.0, 0.5, 0.5)))

    result = evaluate_forward_paper_edge(_historical(), trades, policy=_policy())

    assert result.status is ForwardPaperValidationStatus.FAILED_VALIDATION
    assert ForwardPaperValidationReason.FORWARD_EXPECTANCY_NOT_POSITIVE in result.rejection_reasons
    assert ForwardPaperValidationReason.EDGE_DIRECTION_INCONSISTENT in result.rejection_reasons


def test_excessive_degradation_is_degraded_not_passed() -> None:
    policy = ForwardPaperValidationPolicy(
        minimum_closed_trades=4,
        maximum_expectancy_degradation_from_test=0.5,
    )
    trades = tuple(_trade(index, value) for index, value in enumerate((0.1, 0.1, 0.1, 0.1)))

    result = evaluate_forward_paper_edge(
        _historical(test_expectancy=0.5),
        trades,
        policy=policy,
    )

    assert result.status is ForwardPaperValidationStatus.DEGRADED_VALIDATION
    assert result.rejection_reasons == (
        ForwardPaperValidationReason.EXPECTANCY_DEGRADATION_EXCESSIVE,
    )


def test_unentered_terminal_records_are_excluded() -> None:
    trades = (
        _trade(0, 1.0),
        _trade(1, 1.0),
        _trade(2, -0.5),
        _trade(3, 0.5),
        _trade(4, 0.0, state=PaperTradeState.EXPIRED),
    )

    result = evaluate_forward_paper_edge(_historical(), trades, policy=_policy())

    assert result.forward_profile is not None
    assert result.forward_profile.sample_size == 4


def test_dimension_mismatch_is_machine_readable() -> None:
    result = evaluate_forward_paper_edge(
        _historical(),
        tuple(_trade(index, 1.0) for index in range(4)),
        dimensions={"strategy": StrategyType.TREND_PULLBACK.value, "symbol": "ETHUSDT"},
        policy=_policy(),
    )

    assert result.status is ForwardPaperValidationStatus.INSUFFICIENT_SAMPLE
    assert ForwardPaperValidationReason.SEGMENT_DIMENSIONS_MISMATCH in result.rejection_reasons
    assert ForwardPaperValidationReason.FORWARD_SAMPLE_INSUFFICIENT in result.rejection_reasons


def test_invalid_forward_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        ForwardPaperValidationPolicy(minimum_closed_trades=0)
