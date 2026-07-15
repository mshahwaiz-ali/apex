"""Combine historical and forward-paper evidence for futures eligibility."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from apex.config.strategy_approval import StrategyApprovalConfig
from apex.domain import AccountPolicyDecision, EntryState, RiskMode
from apex.scoring.approval import SetupEligibility
from apex.scoring.historical_approval import (
    EvidenceAwareStrategyApprovalDecision,
    HistoricalEdgeValidationView,
    evaluate_strategy_approval_with_historical_evidence,
)
from apex.scoring.setup_segment import SetupSegmentIdentity
from apex.strategies import StrategyType


class _ValueEnum(Protocol):
    @property
    def value(self) -> str: ...


class ForwardPaperProfileView(Protocol):
    """Structural profile view consumed from forward-paper validation."""

    @property
    def dimensions(self) -> Mapping[str, str]: ...

    @property
    def sample_size(self) -> int: ...

    @property
    def win_rate(self) -> float: ...

    @property
    def expectancy(self) -> float: ...

    @property
    def profit_factor(self) -> float | None: ...

    @property
    def maximum_drawdown_r(self) -> float: ...


class ForwardPaperValidationView(Protocol):
    """Structural view consumed from a forward-paper validation result."""

    @property
    def dimensions(self) -> Mapping[str, str]: ...

    @property
    def status(self) -> _ValueEnum: ...

    @property
    def forward_profile(self) -> ForwardPaperProfileView | None: ...

    @property
    def expectancy_degradation_from_test(self) -> float | None: ...

    @property
    def consistent_edge_direction(self) -> bool: ...

    @property
    def evidence_stable(self) -> bool: ...

    @property
    def promoted_evidence_quality(self) -> _ValueEnum | None: ...

    @property
    def rejection_reasons(self) -> Sequence[_ValueEnum]: ...

    @property
    def warnings(self) -> Sequence[_ValueEnum]: ...


class ForwardApprovalReasonCode(StrEnum):
    """Stable forward-paper eligibility reason codes."""

    FORWARD_PAPER_EVIDENCE_VALIDATED = "FORWARD_PAPER_EVIDENCE_VALIDATED"
    FORWARD_PAPER_EVIDENCE_INSUFFICIENT = "FORWARD_PAPER_EVIDENCE_INSUFFICIENT"
    FORWARD_PAPER_EVIDENCE_FAILED = "FORWARD_PAPER_EVIDENCE_FAILED"
    FORWARD_PAPER_SEGMENT_MISMATCH = "FORWARD_PAPER_SEGMENT_MISMATCH"


@dataclass(frozen=True, slots=True)
class ForwardApprovalReason:
    """One machine-readable forward-paper eligibility explanation."""

    code: ForwardApprovalReasonCode
    message: str

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("forward approval reason message cannot be empty")

    def to_payload(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message}


@dataclass(frozen=True, slots=True)
class ForwardPaperEvidenceAttachment:
    """Immutable futures-approval snapshot of forward-paper validation."""

    dimensions: tuple[tuple[str, str], ...]
    status: str
    sample_size: int | None
    win_rate: float | None
    expectancy: float | None
    profit_factor: float | None
    maximum_drawdown_r: float | None
    expectancy_degradation_from_test: float | None
    consistent_edge_direction: bool
    evidence_stable: bool
    promoted_evidence_quality: str | None
    rejection_reasons: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.status.strip():
            raise ValueError("forward-paper evidence status cannot be empty")
        if self.sample_size is not None and self.sample_size < 1:
            raise ValueError("forward-paper evidence sample size must be positive")

    def to_payload(self) -> dict[str, object]:
        return {
            "dimensions": dict(self.dimensions),
            "status": self.status,
            "sample_size": self.sample_size,
            "win_rate": self.win_rate,
            "expectancy": self.expectancy,
            "profit_factor": self.profit_factor,
            "maximum_drawdown_r": self.maximum_drawdown_r,
            "expectancy_degradation_from_test": self.expectancy_degradation_from_test,
            "consistent_edge_direction": self.consistent_edge_direction,
            "evidence_stable": self.evidence_stable,
            "promoted_evidence_quality": self.promoted_evidence_quality,
            "rejection_reasons": list(self.rejection_reasons),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class ForwardEvidenceAwareStrategyApprovalDecision:
    """Historical approval plus exact-segment forward-paper eligibility."""

    historical_decision: EvidenceAwareStrategyApprovalDecision
    eligibility: SetupEligibility
    forward_paper_evidence: ForwardPaperEvidenceAttachment | None
    forward_paper_reasons: tuple[ForwardApprovalReason, ...]

    def __post_init__(self) -> None:
        if self.approved is (self.eligibility is SetupEligibility.REJECTED):
            raise ValueError("effective eligibility must agree with base approval")
        if not self.approved and self.forward_paper_reasons:
            raise ValueError("rejected base decisions cannot add forward-paper reasons")

    @property
    def approved(self) -> bool:
        return self.historical_decision.approved

    def to_payload(self) -> dict[str, object]:
        payload = self.historical_decision.to_payload()
        payload["eligibility"] = self.eligibility.value
        payload["forward_paper_evidence"] = (
            self.forward_paper_evidence.to_payload()
            if self.forward_paper_evidence is not None
            else None
        )
        payload["forward_paper_evidence_reasons"] = [
            reason.to_payload() for reason in self.forward_paper_reasons
        ]
        payload["effective_eligibility"] = self.eligibility.value
        return payload


def evaluate_strategy_approval_with_forward_paper_evidence(
    *,
    strategy: StrategyType,
    risk_mode: RiskMode,
    score: float,
    entry_state: EntryState,
    config: StrategyApprovalConfig,
    setup_segment: SetupSegmentIdentity,
    historical_edge_validation: HistoricalEdgeValidationView,
    forward_paper_validation: ForwardPaperValidationView,
    account_policy_decision: AccountPolicyDecision | None = None,
) -> ForwardEvidenceAwareStrategyApprovalDecision:
    """Apply exact-segment historical and forward-paper eligibility gates."""

    historical = evaluate_strategy_approval_with_historical_evidence(
        strategy=strategy,
        risk_mode=risk_mode,
        score=score,
        entry_state=entry_state,
        config=config,
        account_policy_decision=account_policy_decision,
        historical_edge_validation=historical_edge_validation,
    )
    attachment = _build_forward_attachment(forward_paper_validation)

    if not historical.approved:
        return ForwardEvidenceAwareStrategyApprovalDecision(
            historical_decision=historical,
            eligibility=SetupEligibility.REJECTED,
            forward_paper_evidence=attachment,
            forward_paper_reasons=(),
        )

    if risk_mode is not RiskMode.STANDARD:
        return ForwardEvidenceAwareStrategyApprovalDecision(
            historical_decision=historical,
            eligibility=historical.eligibility,
            forward_paper_evidence=attachment,
            forward_paper_reasons=(),
        )

    expected_dimensions = dict(setup_segment.to_dimensions())
    historical_dimensions = (
        dict(historical.historical_evidence.dimensions)
        if historical.historical_evidence is not None
        else None
    )
    forward_dimensions = dict(attachment.dimensions) if attachment is not None else None

    dimensions_match = (
        historical_dimensions == expected_dimensions and forward_dimensions == expected_dimensions
    )
    if not dimensions_match:
        return ForwardEvidenceAwareStrategyApprovalDecision(
            historical_decision=historical,
            eligibility=SetupEligibility.PAPER_ONLY,
            forward_paper_evidence=attachment,
            forward_paper_reasons=(
                ForwardApprovalReason(
                    code=ForwardApprovalReasonCode.FORWARD_PAPER_SEGMENT_MISMATCH,
                    message=(
                        "Historical and forward-paper evidence must exactly match "
                        "the requested setup segment."
                    ),
                ),
            ),
        )

    if attachment is None:
        return ForwardEvidenceAwareStrategyApprovalDecision(
            historical_decision=historical,
            eligibility=SetupEligibility.PAPER_ONLY,
            forward_paper_evidence=None,
            forward_paper_reasons=(
                ForwardApprovalReason(
                    code=ForwardApprovalReasonCode.FORWARD_PAPER_EVIDENCE_INSUFFICIENT,
                    message="No matching forward-paper validation result is attached.",
                ),
            ),
        )

    passed = (
        attachment.status == "PASSED_VALIDATION"
        and attachment.promoted_evidence_quality == "VALIDATED_FORWARD_PAPER"
        and attachment.evidence_stable
        and attachment.sample_size is not None
    )
    if passed:
        return ForwardEvidenceAwareStrategyApprovalDecision(
            historical_decision=historical,
            eligibility=SetupEligibility.FUNDED_ELIGIBLE,
            forward_paper_evidence=attachment,
            forward_paper_reasons=(
                ForwardApprovalReason(
                    code=ForwardApprovalReasonCode.FORWARD_PAPER_EVIDENCE_VALIDATED,
                    message=(
                        "The exact setup segment passed historical and forward-paper "
                        "eligibility gates."
                    ),
                ),
            ),
        )

    insufficient_statuses = {"INSUFFICIENT_SAMPLE"}
    reason_code = (
        ForwardApprovalReasonCode.FORWARD_PAPER_EVIDENCE_INSUFFICIENT
        if attachment.status in insufficient_statuses
        else ForwardApprovalReasonCode.FORWARD_PAPER_EVIDENCE_FAILED
    )
    return ForwardEvidenceAwareStrategyApprovalDecision(
        historical_decision=historical,
        eligibility=SetupEligibility.PAPER_ONLY,
        forward_paper_evidence=attachment,
        forward_paper_reasons=(
            ForwardApprovalReason(
                code=reason_code,
                message=(
                    f"Forward-paper validation status {attachment.status} cannot "
                    "advance setup eligibility."
                ),
            ),
        ),
    )


def _build_forward_attachment(
    validation: ForwardPaperValidationView | None,
) -> ForwardPaperEvidenceAttachment | None:
    if validation is None:
        return None

    profile = validation.forward_profile
    return ForwardPaperEvidenceAttachment(
        dimensions=tuple(sorted(validation.dimensions.items())),
        status=validation.status.value,
        sample_size=profile.sample_size if profile is not None else None,
        win_rate=profile.win_rate if profile is not None else None,
        expectancy=profile.expectancy if profile is not None else None,
        profit_factor=profile.profit_factor if profile is not None else None,
        maximum_drawdown_r=(profile.maximum_drawdown_r if profile is not None else None),
        expectancy_degradation_from_test=(validation.expectancy_degradation_from_test),
        consistent_edge_direction=validation.consistent_edge_direction,
        evidence_stable=validation.evidence_stable,
        promoted_evidence_quality=(
            validation.promoted_evidence_quality.value
            if validation.promoted_evidence_quality is not None
            else None
        ),
        rejection_reasons=tuple(reason.value for reason in validation.rejection_reasons),
        warnings=tuple(reason.value for reason in validation.warnings),
    )
