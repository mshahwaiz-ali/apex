from __future__ import annotations

import math

import pytest

from apex.backtesting.calibration_acceptance import (
    AcceptanceState,
    CalibrationAcceptancePolicy,
    evaluate_calibration_acceptance,
)
from apex.backtesting.calibration_metrics import (
    AlignmentClass,
    CalibratedTradeOutcome,
    OutcomeState,
    build_calibration_report,
    calculate_calibration_metrics,
)


def _outcome(
    *,
    realized_r: float,
    state: OutcomeState,
    strategy: str = "breakout",
    regime: str = "trend",
    confidence: str = "high",
    actionability: str = "ready_now",
    alignment: AlignmentClass = AlignmentClass.ALIGNED,
    tp1: bool = False,
    tp2: bool = False,
    runner: bool = False,
    stop: bool = False,
    false_cmp: bool = False,
    fees_r: float = 0.05,
    slippage_r: float = 0.02,
    failure: bool = False,
) -> CalibratedTradeOutcome:
    return CalibratedTradeOutcome(
        strategy=strategy,
        regime=regime,
        confidence_band=confidence,
        actionability_state=actionability,
        alignment=alignment,
        outcome_state=state,
        realized_r=realized_r,
        mfe_r=max(realized_r, 0.0) + 0.5,
        mae_r=max(-realized_r, 0.0) + 0.2,
        tp1_hit=tp1,
        tp2_hit=tp2,
        runner_success=runner,
        stop_hit=stop,
        false_cmp_signal=false_cmp,
        fees_r=fees_r,
        slippage_r=slippage_r,
        liquidation_or_margin_failure=failure,
    )


def test_metrics_include_costs_and_do_not_count_missed_trade_as_win() -> None:
    outcomes = (
        _outcome(
            realized_r=2.0,
            state=OutcomeState.WIN,
            tp1=True,
            tp2=True,
            runner=True,
        ),
        _outcome(
            realized_r=-1.0,
            state=OutcomeState.LOSS,
            stop=True,
            false_cmp=True,
        ),
        _outcome(realized_r=0.0, state=OutcomeState.MISSED),
    )

    metrics = calculate_calibration_metrics(outcomes)

    assert metrics.total_observations == 3
    assert metrics.counted_trades == 2
    assert metrics.wins == 1
    assert metrics.losses == 1
    assert metrics.missed == 1
    assert metrics.win_rate == pytest.approx(0.5)
    assert metrics.expectancy_r == pytest.approx(0.43)
    assert metrics.average_r == metrics.expectancy_r
    assert metrics.tp1_hit_rate == pytest.approx(0.5)
    assert metrics.false_cmp_signal_rate == pytest.approx(1 / 3)
    assert metrics.total_fees_r == pytest.approx(0.1)
    assert metrics.total_slippage_r == pytest.approx(0.04)


def test_profit_factor_is_infinite_when_there_are_no_losses() -> None:
    metrics = calculate_calibration_metrics(
        (
            _outcome(realized_r=1.0, state=OutcomeState.WIN),
            _outcome(realized_r=2.0, state=OutcomeState.WIN),
        )
    )

    assert metrics.profit_factor is not None
    assert math.isinf(metrics.profit_factor)


def test_report_contains_all_required_performance_dimensions() -> None:
    outcomes = (
        _outcome(realized_r=1.0, state=OutcomeState.WIN),
        _outcome(
            realized_r=-1.0,
            state=OutcomeState.LOSS,
            strategy="reversal",
            regime="range",
            confidence="medium",
            actionability="wait_for_retest",
            alignment=AlignmentClass.COUNTERTREND,
        ),
    )

    report = build_calibration_report(outcomes)

    assert {item.value for item in report.by_strategy} == {"breakout", "reversal"}
    assert {item.value for item in report.by_regime} == {"range", "trend"}
    assert {item.value for item in report.by_confidence_band} == {"high", "medium"}
    assert {item.value for item in report.by_actionability_state} == {
        "ready_now",
        "wait_for_retest",
    }
    assert {item.value for item in report.by_alignment} == {
        "aligned",
        "countertrend",
    }


def test_acceptance_rejects_high_tp1_rate_with_negative_expectancy() -> None:
    outcomes = tuple(
        _outcome(
            realized_r=0.2 if index < 8 else -2.0,
            state=OutcomeState.WIN if index < 8 else OutcomeState.LOSS,
            tp1=True,
            stop=index >= 8,
            fees_r=0.0,
            slippage_r=0.0,
        )
        for index in range(10)
    )
    report = build_calibration_report(outcomes)

    result = evaluate_calibration_acceptance(
        report,
        policy=CalibrationAcceptancePolicy(
            minimum_counted_trades=10,
            minimum_regime_trades=5,
            minimum_stable_regime_fraction=1.0,
        ),
    )

    assert report.overall.tp1_hit_rate == 1.0
    assert report.overall.expectancy_r is not None
    assert report.overall.expectancy_r < 0
    assert result.state is AcceptanceState.REJECTED
    assert result.confidence_claims_allowed is False
    assert any("expectancy" in reason for reason in result.reasons)


def test_acceptance_blocks_user_facing_claims_for_small_sample() -> None:
    report = build_calibration_report((_outcome(realized_r=1.0, state=OutcomeState.WIN),))

    result = evaluate_calibration_acceptance(
        report,
        policy=CalibrationAcceptancePolicy(minimum_counted_trades=20),
    )

    assert result.state is AcceptanceState.INSUFFICIENT_SAMPLE
    assert result.confidence_claims_allowed is False
    assert result.stable_regime_fraction is None


def test_acceptance_requires_stable_regime_performance() -> None:
    outcomes = tuple(
        _outcome(
            realized_r=1.0,
            state=OutcomeState.WIN,
            regime="trend",
            fees_r=0.0,
            slippage_r=0.0,
        )
        for _ in range(10)
    ) + tuple(
        _outcome(
            realized_r=-1.0,
            state=OutcomeState.LOSS,
            regime="range",
            fees_r=0.0,
            slippage_r=0.0,
        )
        for _ in range(10)
    )
    report = build_calibration_report(outcomes)

    result = evaluate_calibration_acceptance(
        report,
        policy=CalibrationAcceptancePolicy(
            minimum_counted_trades=20,
            minimum_regime_trades=10,
            minimum_stable_regime_fraction=0.75,
            maximum_stop_rate=1.0,
            maximum_false_cmp_signal_rate=1.0,
        ),
    )

    assert result.state is AcceptanceState.REJECTED
    assert result.stable_regime_fraction == pytest.approx(0.5)
    assert any("stable regime fraction" in reason for reason in result.reasons)


def test_acceptance_allows_claims_only_after_all_gates_pass() -> None:
    outcomes = tuple(
        _outcome(
            realized_r=1.5,
            state=OutcomeState.WIN,
            regime="trend" if index < 10 else "range",
            tp1=True,
            tp2=True,
            runner=True,
            fees_r=0.05,
            slippage_r=0.02,
        )
        for index in range(20)
    )
    report = build_calibration_report(outcomes)

    result = evaluate_calibration_acceptance(
        report,
        policy=CalibrationAcceptancePolicy(
            minimum_counted_trades=20,
            minimum_regime_trades=10,
            minimum_stable_regime_fraction=1.0,
        ),
    )

    assert result.state is AcceptanceState.ACCEPTED
    assert result.confidence_claims_allowed is True
    assert result.reasons == ()
    assert result.stable_regime_fraction == 1.0


def test_outcome_validation_rejects_invalid_measurements() -> None:
    with pytest.raises(ValueError, match="mfe_r"):
        CalibratedTradeOutcome(
            strategy="breakout",
            regime="trend",
            confidence_band="high",
            actionability_state="ready_now",
            alignment=AlignmentClass.ALIGNED,
            outcome_state=OutcomeState.WIN,
            realized_r=1.0,
            mfe_r=-1.0,
            mae_r=0.2,
            tp1_hit=True,
            tp2_hit=False,
            runner_success=False,
            stop_hit=False,
            false_cmp_signal=False,
        )
