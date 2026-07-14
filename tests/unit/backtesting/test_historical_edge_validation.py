"""Tests for deterministic out-of-sample historical edge evaluation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.backtesting import (
    BacktestOutcome,
    BacktestSignal,
    EvidenceQuality,
    HistoricalEdgeValidationPolicy,
    HistoricalEdgeValidationReason,
    HistoricalEdgeValidationStatus,
    SimulatedTrade,
    build_historical_edge_profile,
    validate_out_of_sample_edges,
)
from apex.strategies import StrategyType, TradeDirection


def _trade(index: int, realized_r: float, *, symbol: str = "BTC/USDT") -> SimulatedTrade:
    generated_at = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(hours=index)
    signal = BacktestSignal(
        symbol=symbol,
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
    return SimulatedTrade(
        signal=signal,
        outcome=BacktestOutcome.TARGET if realized_r > 0.0 else BacktestOutcome.STOP,
        exit_time=generated_at + timedelta(minutes=30),
        exit_price=102.0 if realized_r > 0.0 else 99.0,
        gross_pnl=realized_r + 0.01,
        fees=0.01,
        net_pnl=realized_r,
        realized_r_multiple=realized_r,
        holding_candles=6,
    )


def _profile(
    sample_size: int,
    realized_r: float,
    *,
    symbol: str = "BTC/USDT",
    dimension_name: str = "symbol",
):
    return build_historical_edge_profile(
        tuple(_trade(index, realized_r, symbol=symbol) for index in range(sample_size)),
        dimensions={dimension_name: symbol},
    )


def _validate(
    *,
    train=None,
    validation=None,
    test=None,
    policy: HistoricalEdgeValidationPolicy | None = None,
):
    return validate_out_of_sample_edges(
        (train or _profile(100, 1.0),),
        (validation or _profile(50, 0.75),),
        (test or _profile(50, 0.60),),
        policy=policy,
    )[0]


def test_successful_out_of_sample_promotion_preserves_profiles() -> None:
    train = _profile(100, 1.0)
    validation = _profile(50, 0.75)
    test = _profile(50, 0.60)

    result = _validate(train=train, validation=validation, test=test)

    assert result.status is HistoricalEdgeValidationStatus.PASSED_VALIDATION
    assert result.promoted_evidence_quality is EvidenceQuality.VALIDATED_OUT_OF_SAMPLE
    assert result.out_of_sample_sample_size == 100
    assert result.validation_expectancy_degradation == pytest.approx(0.25)
    assert result.test_expectancy_degradation == pytest.approx(0.40)
    assert result.consistent_edge_direction is True
    assert result.evidence_stable is True
    assert result.train_profile is train
    assert result.validation_profile is validation
    assert result.test_profile is test
    assert result.warnings == (
        HistoricalEdgeValidationReason.FORWARD_PAPER_VALIDATION_REQUIRED,
    )


@pytest.mark.parametrize(
    ("validation_size", "test_size", "expected_reason"),
    (
        (49, 51, HistoricalEdgeValidationReason.VALIDATION_SAMPLE_INSUFFICIENT),
        (51, 49, HistoricalEdgeValidationReason.TEST_SAMPLE_INSUFFICIENT),
    ),
)
def test_individual_out_of_sample_minimums_are_enforced(
    validation_size: int,
    test_size: int,
    expected_reason: HistoricalEdgeValidationReason,
) -> None:
    result = _validate(
        validation=_profile(validation_size, 0.75),
        test=_profile(test_size, 0.60),
    )

    assert result.status is HistoricalEdgeValidationStatus.INSUFFICIENT_OUT_OF_SAMPLE
    assert expected_reason in result.rejection_reasons
    assert result.promoted_evidence_quality is None


@pytest.mark.parametrize(
    ("validation_profiles", "test_profiles", "expected_reason"),
    (
        ((), (_profile(50, 0.60),), HistoricalEdgeValidationReason.MISSING_VALIDATION_SEGMENT),
        ((_profile(50, 0.75),), (), HistoricalEdgeValidationReason.MISSING_TEST_SEGMENT),
    ),
)
def test_missing_out_of_sample_segment_is_reported(
    validation_profiles,
    test_profiles,
    expected_reason: HistoricalEdgeValidationReason,
) -> None:
    result = validate_out_of_sample_edges(
        (_profile(100, 1.0),), validation_profiles, test_profiles
    )[0]

    assert result.status is HistoricalEdgeValidationStatus.INSUFFICIENT_OUT_OF_SAMPLE
    assert expected_reason in result.rejection_reasons


@pytest.mark.parametrize(
    ("validation_r", "test_r", "expected_reason"),
    (
        (-0.25, 0.60, HistoricalEdgeValidationReason.VALIDATION_EXPECTANCY_NOT_POSITIVE),
        (0.75, -0.25, HistoricalEdgeValidationReason.TEST_EXPECTANCY_NOT_POSITIVE),
    ),
)
def test_non_positive_out_of_sample_expectancy_fails(
    validation_r: float,
    test_r: float,
    expected_reason: HistoricalEdgeValidationReason,
) -> None:
    result = _validate(
        validation=_profile(50, validation_r),
        test=_profile(50, test_r),
    )

    assert result.status is HistoricalEdgeValidationStatus.FAILED_VALIDATION
    assert expected_reason in result.rejection_reasons
    assert HistoricalEdgeValidationReason.EDGE_DIRECTION_INCONSISTENT in result.rejection_reasons


def test_profit_factor_failure_is_machine_readable() -> None:
    mixed = tuple(
        _trade(index, 1.0 if index < 20 else -1.0) for index in range(50)
    )
    validation = build_historical_edge_profile(mixed, dimensions={"symbol": "BTC/USDT"})
    result = _validate(validation=validation)

    assert result.status is HistoricalEdgeValidationStatus.FAILED_VALIDATION
    assert (
        HistoricalEdgeValidationReason.VALIDATION_PROFIT_FACTOR_INADEQUATE
        in result.rejection_reasons
    )


@pytest.mark.parametrize(
    ("validation_r", "test_r", "expected_reason"),
    (
        (0.49, 0.60, HistoricalEdgeValidationReason.VALIDATION_EXPECTANCY_DEGRADATION_EXCESSIVE),
        (0.75, 0.39, HistoricalEdgeValidationReason.TEST_EXPECTANCY_DEGRADATION_EXCESSIVE),
    ),
)
def test_excessive_expectancy_degradation_is_not_promoted(
    validation_r: float,
    test_r: float,
    expected_reason: HistoricalEdgeValidationReason,
) -> None:
    result = _validate(
        validation=_profile(50, validation_r),
        test=_profile(50, test_r),
    )

    assert result.status is HistoricalEdgeValidationStatus.DEGRADED_VALIDATION
    assert result.rejection_reasons == (expected_reason,)
    assert result.promoted_evidence_quality is None


def test_results_are_ordered_by_stable_dimension_key() -> None:
    results = validate_out_of_sample_edges(
        (_profile(100, 1.0, symbol="ETH/USDT"), _profile(100, 1.0)),
        (_profile(50, 0.75, symbol="ETH/USDT"), _profile(50, 0.75)),
        (_profile(50, 0.60, symbol="ETH/USDT"), _profile(50, 0.60)),
    )

    assert tuple(result.dimensions["symbol"] for result in results) == (
        "BTC/USDT",
        "ETH/USDT",
    )


def test_mismatched_dimension_identity_cannot_be_combined() -> None:
    results = validate_out_of_sample_edges(
        (_profile(100, 1.0),),
        (_profile(50, 0.75, dimension_name="market"),),
        (_profile(50, 0.60),),
    )

    assert len(results) == 2
    assert all(
        result.status is HistoricalEdgeValidationStatus.INSUFFICIENT_OUT_OF_SAMPLE
        for result in results
    )
    assert any(
        HistoricalEdgeValidationReason.MISSING_VALIDATION_SEGMENT
        in result.rejection_reasons
        for result in results
    )
    assert any(
        HistoricalEdgeValidationReason.MISSING_TRAIN_SEGMENT in result.rejection_reasons
        for result in results
    )


def test_no_forward_paper_or_production_promotion_is_possible() -> None:
    result = _validate()

    assert result.promoted_evidence_quality is EvidenceQuality.VALIDATED_OUT_OF_SAMPLE
    assert result.promoted_evidence_quality not in {
        EvidenceQuality.VALIDATED_FORWARD_PAPER,
        EvidenceQuality.PRODUCTION_ELIGIBLE,
    }


def test_empty_profile_sets_return_no_results() -> None:
    assert validate_out_of_sample_edges((), (), ()) == ()


def test_invalid_policy_and_duplicate_segments_are_rejected() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        HistoricalEdgeValidationPolicy(minimum_validation_trades=0)

    profile = _profile(100, 1.0)
    with pytest.raises(ValueError, match="duplicate train"):
        validate_out_of_sample_edges((profile, profile), (), ())
