"""Untouched final-test evaluation for preselected calibration candidates."""

from __future__ import annotations

from collections.abc import Mapping

from apex.calibration.contracts import (
    CalibrationDecision,
    CalibrationMetrics,
    CalibrationPolicy,
    CalibrationReason,
    FinalTestAssessment,
    WalkForwardCalibrationReport,
)


def attach_final_test_results(
    report: WalkForwardCalibrationReport,
    *,
    baseline_metrics_by_candidate: Mapping[str, CalibrationMetrics],
    candidate_metrics_by_candidate: Mapping[str, CalibrationMetrics],
    validation_expectancy_by_candidate: Mapping[str, float],
    policy: CalibrationPolicy | None = None,
) -> WalkForwardCalibrationReport:
    """Attach final-test results without changing preselection membership."""

    resolved_policy = policy or CalibrationPolicy()
    selected = set(report.selected_candidate_ids)
    supplied = set(candidate_metrics_by_candidate)
    if supplied != selected:
        raise ValueError("final-test candidate metrics must cover selected candidates exactly")
    if set(baseline_metrics_by_candidate) != selected:
        raise ValueError("final-test baseline metrics must cover selected candidates exactly")
    if set(validation_expectancy_by_candidate) != selected:
        raise ValueError("validation expectancy must cover selected candidates exactly")

    final_assessments = tuple(
        _evaluate_final_test(
            candidate_id,
            baseline_metrics_by_candidate[candidate_id],
            candidate_metrics_by_candidate[candidate_id],
            validation_expectancy_by_candidate[candidate_id],
            resolved_policy,
        )
        for candidate_id in sorted(selected)
    )
    return WalkForwardCalibrationReport(
        report_id=report.report_id,
        assessments=report.assessments,
        selected_candidate_ids=report.selected_candidate_ids,
        final_test_assessments=final_assessments,
        warnings=(
            *report.warnings,
            "final-test data was evaluated only after candidate selection",
        ),
    )


def _evaluate_final_test(
    candidate_id: str,
    baseline: CalibrationMetrics,
    candidate: CalibrationMetrics,
    validation_expectancy: float,
    policy: CalibrationPolicy,
) -> FinalTestAssessment:
    degradation = None
    if validation_expectancy > 0.0:
        degradation = (validation_expectancy - candidate.expectancy) / validation_expectancy

    reasons: list[CalibrationReason] = []
    degraded = candidate.expectancy <= 0.0
    if degradation is not None:
        degraded = degraded or (
            degradation > policy.maximum_final_test_expectancy_degradation
        )
    degraded = degraded or candidate.maximum_drawdown_r > baseline.maximum_drawdown_r
    if degraded:
        decision = CalibrationDecision.REJECT
        reasons.append(CalibrationReason.FINAL_TEST_DEGRADED)
    else:
        decision = CalibrationDecision.ACCEPT
        reasons.append(CalibrationReason.CHANGE_ACCEPTED)

    return FinalTestAssessment(
        candidate_id=candidate_id,
        decision=decision,
        baseline_metrics=baseline,
        candidate_metrics=candidate,
        expectancy_degradation_from_validation=degradation,
        reasons=tuple(reasons),
    )
