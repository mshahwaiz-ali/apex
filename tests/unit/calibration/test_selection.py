"""Tests for train/validation-only calibration selection."""

from __future__ import annotations

from apex.calibration import (
    CalibrationCandidate,
    CalibrationDecision,
    CalibrationMetrics,
    CalibrationPolicy,
    CalibrationReason,
    select_calibration_candidates,
)


def _metrics(
    *,
    sample_size: int,
    expectancy: float,
    drawdown: float,
    symbol_delta: float = 0.0,
    regime_delta: float = 0.0,
) -> CalibrationMetrics:
    return CalibrationMetrics(
        sample_size=sample_size,
        expectancy=expectancy,
        maximum_drawdown_r=drawdown,
        expectancy_by_symbol={
            "BTCUSDT": expectancy + symbol_delta,
            "ETHUSDT": expectancy - symbol_delta,
        },
        expectancy_by_regime={
            "trend": expectancy + regime_delta,
            "range": expectancy - regime_delta,
        },
    )


def _candidate(
    identifier: str = "candidate-a",
    *,
    train_sample: int = 150,
    validation_sample: int = 80,
    validation_expectancy: float = 0.45,
    validation_drawdown: float = 7.0,
    unstable_symbol: bool = False,
) -> CalibrationCandidate:
    candidate_validation = _metrics(
        sample_size=validation_sample,
        expectancy=validation_expectancy,
        drawdown=validation_drawdown,
    )
    if unstable_symbol:
        candidate_validation = CalibrationMetrics(
            sample_size=validation_sample,
            expectancy=validation_expectancy,
            maximum_drawdown_r=validation_drawdown,
            expectancy_by_symbol={"BTCUSDT": 0.8, "ETHUSDT": -0.2},
            expectancy_by_regime={"trend": 0.6, "range": 0.3},
        )
    return CalibrationCandidate(
        identifier=identifier,
        strategy="trend_pullback",
        parameter_changes={"minimum_score": 78},
        baseline_train=_metrics(sample_size=150, expectancy=0.30, drawdown=8.0),
        candidate_train=_metrics(
            sample_size=train_sample,
            expectancy=0.40,
            drawdown=7.0,
        ),
        baseline_validation=_metrics(
            sample_size=80,
            expectancy=0.30,
            drawdown=8.0,
        ),
        candidate_validation=candidate_validation,
    )


def _policy() -> CalibrationPolicy:
    return CalibrationPolicy(
        minimum_train_trades=100,
        minimum_validation_trades=50,
        minimum_stable_symbols=2,
        minimum_stable_regimes=2,
    )


def test_accepts_stable_validation_improvement() -> None:
    report = select_calibration_candidates((_candidate(),), policy=_policy())

    assert report.selected_candidate_ids == ("candidate-a",)
    assert report.assessments[0].decision is CalibrationDecision.ACCEPT
    assert report.assessments[0].reasons == (CalibrationReason.CHANGE_ACCEPTED,)


def test_rejects_validation_drawdown_regression() -> None:
    report = select_calibration_candidates(
        (_candidate(validation_drawdown=9.0),),
        policy=_policy(),
    )

    assessment = report.assessments[0]
    assert assessment.decision is CalibrationDecision.REJECT
    assert CalibrationReason.VALIDATION_DRAWDOWN_WORSE in assessment.reasons


def test_rejects_unstable_one_symbol_improvement() -> None:
    report = select_calibration_candidates(
        (_candidate(unstable_symbol=True),),
        policy=_policy(),
    )

    assessment = report.assessments[0]
    assert assessment.decision is CalibrationDecision.REJECT
    assert CalibrationReason.SYMBOL_STABILITY_INSUFFICIENT in assessment.reasons
    assert assessment.stable_symbols == ("BTCUSDT",)


def test_insufficient_train_or_validation_sample_is_distinct() -> None:
    report = select_calibration_candidates(
        (_candidate(train_sample=50, validation_sample=20),),
        policy=_policy(),
    )

    assessment = report.assessments[0]
    assert assessment.decision is CalibrationDecision.INSUFFICIENT_EVIDENCE
    assert CalibrationReason.TRAIN_SAMPLE_INSUFFICIENT in assessment.reasons
    assert CalibrationReason.VALIDATION_SAMPLE_INSUFFICIENT in assessment.reasons


def test_report_identity_is_deterministic_and_result_sensitive() -> None:
    first = select_calibration_candidates((_candidate(),), policy=_policy())
    second = select_calibration_candidates((_candidate(),), policy=_policy())
    changed = select_calibration_candidates(
        (_candidate(validation_expectancy=0.55),),
        policy=_policy(),
    )

    assert first.report_id == second.report_id
    assert first.report_id != changed.report_id
    assert len(first.report_id) == 64


def test_duplicate_candidate_ids_are_rejected() -> None:
    try:
        select_calibration_candidates(
            (_candidate("duplicate"), _candidate("duplicate")),
            policy=_policy(),
        )
    except ValueError as exc:
        assert "identifiers must be unique" in str(exc)
    else:
        raise AssertionError("duplicate calibration candidate ids should fail")
