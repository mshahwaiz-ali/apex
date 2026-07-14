"""Train/validation-only calibration candidate selection."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from apex.calibration.contracts import (
    CalibrationAssessment,
    CalibrationCandidate,
    CalibrationDecision,
    CalibrationPolicy,
    CalibrationReason,
    WalkForwardCalibrationReport,
)


def select_calibration_candidates(
    candidates: Sequence[CalibrationCandidate],
    *,
    policy: CalibrationPolicy | None = None,
) -> WalkForwardCalibrationReport:
    """Select candidates without consulting any final-test result."""

    if not candidates:
        raise ValueError("calibration selection requires at least one candidate")
    identifiers = tuple(candidate.identifier for candidate in candidates)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("calibration candidate identifiers must be unique")
    resolved_policy = policy or CalibrationPolicy()
    assessments = tuple(
        _assess_candidate(candidate, resolved_policy)
        for candidate in sorted(candidates, key=lambda item: item.identifier)
    )
    selected = tuple(
        item.candidate_id
        for item in assessments
        if item.decision is CalibrationDecision.ACCEPT
    )
    payload = {
        "assessments": [_assessment_payload(item) for item in assessments],
        "selected_candidate_ids": list(selected),
    }
    report_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return WalkForwardCalibrationReport(
        report_id=report_id,
        assessments=assessments,
        selected_candidate_ids=selected,
        warnings=(
            "candidate selection used train and validation data only",
            "final-test results must be attached after selection",
        ),
    )


def calibration_report_to_payload(report: WalkForwardCalibrationReport) -> dict[str, object]:
    """Serialize a complete calibration report deterministically."""

    return {
        "schema_version": 1,
        "report_id": report.report_id,
        "assessments": [_assessment_payload(item) for item in report.assessments],
        "selected_candidate_ids": list(report.selected_candidate_ids),
        "final_test_assessments": [
            {
                "candidate_id": item.candidate_id,
                "decision": item.decision.value,
                "baseline_metrics": _metrics_payload(item.baseline_metrics),
                "candidate_metrics": _metrics_payload(item.candidate_metrics),
                "expectancy_degradation_from_validation": (
                    item.expectancy_degradation_from_validation
                ),
                "reasons": [reason.value for reason in item.reasons],
            }
            for item in report.final_test_assessments
        ],
        "warnings": list(report.warnings),
    }


def _assess_candidate(
    candidate: CalibrationCandidate,
    policy: CalibrationPolicy,
) -> CalibrationAssessment:
    reasons: list[CalibrationReason] = []
    if candidate.candidate_train.sample_size < policy.minimum_train_trades:
        reasons.append(CalibrationReason.TRAIN_SAMPLE_INSUFFICIENT)
    if candidate.candidate_validation.sample_size < policy.minimum_validation_trades:
        reasons.append(CalibrationReason.VALIDATION_SAMPLE_INSUFFICIENT)

    expectancy_improvement = (
        candidate.candidate_validation.expectancy
        - candidate.baseline_validation.expectancy
    )
    drawdown_change = (
        candidate.candidate_validation.maximum_drawdown_r
        - candidate.baseline_validation.maximum_drawdown_r
    )
    if expectancy_improvement < policy.minimum_expectancy_improvement:
        reasons.append(CalibrationReason.VALIDATION_EXPECTANCY_NOT_IMPROVED)
    if drawdown_change > policy.maximum_drawdown_increase_r:
        reasons.append(CalibrationReason.VALIDATION_DRAWDOWN_WORSE)

    stable_symbols = _stable_dimensions(
        candidate.baseline_validation.expectancy_by_symbol,
        candidate.candidate_validation.expectancy_by_symbol,
    )
    stable_regimes = _stable_dimensions(
        candidate.baseline_validation.expectancy_by_regime,
        candidate.candidate_validation.expectancy_by_regime,
    )
    if len(stable_symbols) < policy.minimum_stable_symbols:
        reasons.append(CalibrationReason.SYMBOL_STABILITY_INSUFFICIENT)
    if len(stable_regimes) < policy.minimum_stable_regimes:
        reasons.append(CalibrationReason.REGIME_STABILITY_INSUFFICIENT)

    insufficient = {
        CalibrationReason.TRAIN_SAMPLE_INSUFFICIENT,
        CalibrationReason.VALIDATION_SAMPLE_INSUFFICIENT,
    }
    if any(reason in insufficient for reason in reasons):
        decision = CalibrationDecision.INSUFFICIENT_EVIDENCE
    elif reasons:
        decision = CalibrationDecision.REJECT
    else:
        decision = CalibrationDecision.ACCEPT
        reasons.append(CalibrationReason.CHANGE_ACCEPTED)

    return CalibrationAssessment(
        candidate_id=candidate.identifier,
        strategy=candidate.strategy,
        decision=decision,
        validation_expectancy_improvement=expectancy_improvement,
        validation_drawdown_change_r=drawdown_change,
        stable_symbols=stable_symbols,
        stable_regimes=stable_regimes,
        reasons=tuple(reasons),
    )


def _stable_dimensions(
    baseline: Mapping[str, float],
    candidate: Mapping[str, float],
) -> tuple[str, ...]:
    return tuple(
        key
        for key in sorted(set(baseline) & set(candidate))
        if candidate[key] > 0.0 and candidate[key] >= baseline[key]
    )


def _assessment_payload(item: CalibrationAssessment) -> dict[str, object]:
    return {
        "candidate_id": item.candidate_id,
        "strategy": item.strategy,
        "decision": item.decision.value,
        "validation_expectancy_improvement": item.validation_expectancy_improvement,
        "validation_drawdown_change_r": item.validation_drawdown_change_r,
        "stable_symbols": list(item.stable_symbols),
        "stable_regimes": list(item.stable_regimes),
        "reasons": [reason.value for reason in item.reasons],
    }


def _metrics_payload(metrics) -> dict[str, object]:
    return {
        "sample_size": metrics.sample_size,
        "expectancy": metrics.expectancy,
        "maximum_drawdown_r": metrics.maximum_drawdown_r,
        "expectancy_by_symbol": dict(metrics.expectancy_by_symbol),
        "expectancy_by_regime": dict(metrics.expectancy_by_regime),
    }
