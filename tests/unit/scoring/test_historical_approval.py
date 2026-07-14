"""Tests for V1.5 out-of-sample evidence attachment to strategy approval."""

from __future__ import annotations

from pathlib import Path

from apex.backtesting import (
    EvidenceQuality,
    HistoricalEdgeValidationReason,
    HistoricalEdgeValidationResult,
    HistoricalEdgeValidationStatus,
)
from apex.config import load_strategy_approval_config
from apex.domain import EntryState, RiskMode
from apex.scoring import (
    HistoricalApprovalReasonCode,
    SetupEligibility,
    evaluate_strategy_approval_with_historical_evidence,
)
from apex.strategies import StrategyType


def _config():
    return load_strategy_approval_config(Path("config/strategy_approval.yaml"))


def _validation(
    status: HistoricalEdgeValidationStatus,
    *,
    promoted: EvidenceQuality | None = None,
    stable: bool = False,
    reasons: tuple[HistoricalEdgeValidationReason, ...] = (),
) -> HistoricalEdgeValidationResult:
    return HistoricalEdgeValidationResult(
        dimensions={"strategy": StrategyType.TREND_PULLBACK.value},
        status=status,
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
        evidence_stable=stable,
        promoted_evidence_quality=promoted,
        rejection_reasons=reasons,
        warnings=(HistoricalEdgeValidationReason.FORWARD_PAPER_VALIDATION_REQUIRED,)
        if status is HistoricalEdgeValidationStatus.PASSED_VALIDATION
        else (),
    )


def _evaluate(
    validation: HistoricalEdgeValidationResult | None,
    *,
    risk_mode: RiskMode = RiskMode.STANDARD,
    score: float = 80.0,
):
    return evaluate_strategy_approval_with_historical_evidence(
        strategy=StrategyType.TREND_PULLBACK,
        risk_mode=risk_mode,
        score=score,
        entry_state=EntryState.READY_NOW,
        config=_config(),
        historical_edge_validation=validation,
    )


def test_passed_out_of_sample_evidence_is_attached_but_remains_paper_only() -> None:
    result = _evaluate(
        _validation(
            HistoricalEdgeValidationStatus.PASSED_VALIDATION,
            promoted=EvidenceQuality.VALIDATED_OUT_OF_SAMPLE,
            stable=True,
        )
    )

    assert result.approved is True
    assert result.eligibility is SetupEligibility.PAPER_ONLY
    assert result.historical_evidence is not None
    assert result.historical_evidence.status == "PASSED_VALIDATION"
    assert result.historical_evidence.promoted_evidence_quality == "VALIDATED_OUT_OF_SAMPLE"
    assert tuple(reason.code for reason in result.historical_reasons) == (
        HistoricalApprovalReasonCode.OUT_OF_SAMPLE_EVIDENCE_VALIDATED,
        HistoricalApprovalReasonCode.FORWARD_PAPER_EVIDENCE_REQUIRED,
    )


def test_missing_evidence_is_machine_readable() -> None:
    result = _evaluate(None)

    assert result.eligibility is SetupEligibility.PAPER_ONLY
    assert result.historical_evidence is None
    assert result.historical_reasons[0].code is (
        HistoricalApprovalReasonCode.OUT_OF_SAMPLE_EVIDENCE_INSUFFICIENT
    )


def test_insufficient_and_failed_validation_are_distinguished() -> None:
    insufficient = _evaluate(
        _validation(
            HistoricalEdgeValidationStatus.INSUFFICIENT_OUT_OF_SAMPLE,
            reasons=(HistoricalEdgeValidationReason.TEST_SAMPLE_INSUFFICIENT,),
        )
    )
    failed = _evaluate(
        _validation(
            HistoricalEdgeValidationStatus.FAILED_VALIDATION,
            reasons=(HistoricalEdgeValidationReason.TEST_EXPECTANCY_NOT_POSITIVE,),
        )
    )

    assert insufficient.historical_reasons[0].code is (
        HistoricalApprovalReasonCode.OUT_OF_SAMPLE_EVIDENCE_INSUFFICIENT
    )
    assert failed.historical_reasons[0].code is (
        HistoricalApprovalReasonCode.OUT_OF_SAMPLE_EVIDENCE_FAILED
    )


def test_base_rejection_is_preserved_without_evidence_override() -> None:
    result = _evaluate(
        _validation(
            HistoricalEdgeValidationStatus.PASSED_VALIDATION,
            promoted=EvidenceQuality.VALIDATED_OUT_OF_SAMPLE,
            stable=True,
        ),
        score=10.0,
    )

    assert result.approved is False
    assert result.eligibility is SetupEligibility.REJECTED
    assert result.historical_reasons == ()
    assert result.historical_evidence is not None


def test_non_standard_modes_keep_existing_operational_limits() -> None:
    validation = _validation(
        HistoricalEdgeValidationStatus.PASSED_VALIDATION,
        promoted=EvidenceQuality.VALIDATED_OUT_OF_SAMPLE,
        stable=True,
    )

    aggressive = _evaluate(validation, risk_mode=RiskMode.AGGRESSIVE)
    extreme = _evaluate(validation, risk_mode=RiskMode.EXTREME)

    assert aggressive.eligibility is SetupEligibility.PAPER_ONLY
    assert extreme.eligibility is SetupEligibility.EXPERIMENTAL_ONLY
    assert aggressive.historical_reasons == ()
    assert extreme.historical_reasons == ()


def test_payload_serializes_attached_evidence_deterministically() -> None:
    result = _evaluate(
        _validation(
            HistoricalEdgeValidationStatus.PASSED_VALIDATION,
            promoted=EvidenceQuality.VALIDATED_OUT_OF_SAMPLE,
            stable=True,
        )
    )

    payload = result.to_payload()
    evidence = payload["historical_evidence"]
    assert isinstance(evidence, dict)
    assert evidence["dimensions"] == {"strategy": StrategyType.TREND_PULLBACK.value}
    assert payload["eligibility"] == SetupEligibility.PAPER_ONLY.value
