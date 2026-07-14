"""Attach typed out-of-sample evidence to deterministic strategy approval."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from apex.config.strategy_approval import StrategyApprovalConfig
from apex.domain import AccountPolicyDecision, EntryState, RiskMode
from apex.scoring.approval import (
    ApprovalReason,
    ApprovalReasonCode,
    SetupEligibility,
    StrategyApprovalDecision,
    evaluate_strategy_approval,
)
from apex.strategies import StrategyType


class _ValueEnum(Protocol):
    value: str


class HistoricalEdgeValidationView(Protocol):
    """Structural view consumed from a V1.4 validation result."""

    dimensions: Mapping[str, str]
    status: _ValueEnum
    out_of_sample_sample_size: int
    evidence_stable: bool
    promoted_evidence_quality: _ValueEnum | None
    rejection_reasons: Sequence[_ValueEnum]
    warnings: Sequence[_ValueEnum]


class HistoricalApprovalReasonCode(StrEnum):
    """Stable evidence-specific approval reason codes."""

    OUT_OF_SAMPLE_EVIDENCE_VALIDATED = "OUT_OF_SAMPLE_EVIDENCE_VALIDATED"
    OUT_OF_SAMPLE_EVIDENCE_INSUFFICIENT = "OUT_OF_SAMPLE_EVIDENCE_INSUFFICIENT"
    OUT_OF_SAMPLE_EVIDENCE_FAILED = "OUT_OF_SAMPLE_EVIDENCE_FAILED"
    FORWARD_PAPER_EVIDENCE_REQUIRED = "FORWARD_PAPER_EVIDENCE_REQUIRED"


@dataclass(frozen=True, slots=True)
class HistoricalApprovalReason:
    """One evidence-specific explanation attached to strategy approval."""

    code: HistoricalApprovalReasonCode
    message: str

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("historical approval reason message cannot be empty")

    def to_payload(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message}


@dataclass(frozen=True, slots=True)
class HistoricalEvidenceAttachment:
    """Immutable approval snapshot of one V1.4 validation result."""

    dimensions: tuple[tuple[str, str], ...]
    status: str
    out_of_sample_sample_size: int
    evidence_stable: bool
    promoted_evidence_quality: str | None
    rejection_reasons: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.status.strip():
            raise ValueError("historical evidence status cannot be empty")
        if self.out_of_sample_sample_size < 0:
            raise ValueError("historical evidence sample size cannot be negative")

    def to_payload(self) -> dict[str, object]:
        return {
            "dimensions": dict(self.dimensions),
            "status": self.status,
            "out_of_sample_sample_size": self.out_of_sample_sample_size,
            "evidence_stable": self.evidence_stable,
            "promoted_evidence_quality": self.promoted_evidence_quality,
            "rejection_reasons": list(self.rejection_reasons),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class EvidenceAwareStrategyApprovalDecision:
    """Base approval plus attached out-of-sample evidence and effective eligibility."""

    base_decision: StrategyApprovalDecision
    eligibility: SetupEligibility
    historical_evidence: HistoricalEvidenceAttachment | None
    historical_reasons: tuple[HistoricalApprovalReason, ...]

    def __post_init__(self) -> None:
        if self.base_decision.approved is (self.eligibility is SetupEligibility.REJECTED):
            raise ValueError("effective eligibility must agree with base approval")
        if not self.base_decision.approved and self.historical_reasons:
            raise ValueError("rejected base decisions cannot add evidence eligibility reasons")

    @property
    def approved(self) -> bool:
        return self.base_decision.approved

    def to_payload(self) -> dict[str, object]:
        payload = self.base_decision.to_payload()
        payload["eligibility"] = self.eligibility.value
        payload["historical_evidence"] = (
            self.historical_evidence.to_payload()
            if self.historical_evidence is not None
            else None
        )
        payload["historical_evidence_reasons"] = [
            reason.to_payload() for reason in self.historical_reasons
        ]
        return payload


def evaluate_strategy_approval_with_historical_evidence(
    *,
    strategy: StrategyType,
    risk_mode: RiskMode,
    score: float,
    entry_state: EntryState,
    config: StrategyApprovalConfig,
    account_policy_decision: AccountPolicyDecision | None = None,
    historical_edge_validation: HistoricalEdgeValidationView | None = None,
) -> EvidenceAwareStrategyApprovalDecision:
    """Evaluate approval and attach real V1.4 evidence without funded promotion."""

    base = evaluate_strategy_approval(
        strategy=strategy,
        risk_mode=risk_mode,
        score=score,
        entry_state=entry_state,
        config=config,
        account_policy_decision=account_policy_decision,
        historical_evidence_available=False,
    )
    attachment = _build_attachment(historical_edge_validation)

    if not base.approved:
        return EvidenceAwareStrategyApprovalDecision(
            base_decision=base,
            eligibility=SetupEligibility.REJECTED,
            historical_evidence=attachment,
            historical_reasons=(),
        )

    if risk_mode is not RiskMode.STANDARD:
        return EvidenceAwareStrategyApprovalDecision(
            base_decision=base,
            eligibility=base.eligibility,
            historical_evidence=attachment,
            historical_reasons=(),
        )

    reasons = _historical_reasons(attachment)
    return EvidenceAwareStrategyApprovalDecision(
        base_decision=base,
        eligibility=SetupEligibility.PAPER_ONLY,
        historical_evidence=attachment,
        historical_reasons=reasons,
    )


def _build_attachment(
    validation: HistoricalEdgeValidationView | None,
) -> HistoricalEvidenceAttachment | None:
    if validation is None:
        return None
    return HistoricalEvidenceAttachment(
        dimensions=tuple(sorted(validation.dimensions.items())),
        status=validation.status.value,
        out_of_sample_sample_size=validation.out_of_sample_sample_size,
        evidence_stable=validation.evidence_stable,
        promoted_evidence_quality=(
            validation.promoted_evidence_quality.value
            if validation.promoted_evidence_quality is not None
            else None
        ),
        rejection_reasons=tuple(reason.value for reason in validation.rejection_reasons),
        warnings=tuple(reason.value for reason in validation.warnings),
    )


def _historical_reasons(
    attachment: HistoricalEvidenceAttachment | None,
) -> tuple[HistoricalApprovalReason, ...]:
    if attachment is None:
        return (
            HistoricalApprovalReason(
                code=HistoricalApprovalReasonCode.OUT_OF_SAMPLE_EVIDENCE_INSUFFICIENT,
                message="No setup-specific out-of-sample validation result is attached.",
            ),
        )

    if (
        attachment.status == "PASSED_VALIDATION"
        and attachment.promoted_evidence_quality == "VALIDATED_OUT_OF_SAMPLE"
        and attachment.evidence_stable
    ):
        return (
            HistoricalApprovalReason(
                code=HistoricalApprovalReasonCode.OUT_OF_SAMPLE_EVIDENCE_VALIDATED,
                message="The matching setup segment passed out-of-sample validation.",
            ),
            HistoricalApprovalReason(
                code=HistoricalApprovalReasonCode.FORWARD_PAPER_EVIDENCE_REQUIRED,
                message="Forward-paper evidence is still required for later eligibility gates.",
            ),
        )

    insufficient_statuses = {"INSUFFICIENT_OUT_OF_SAMPLE"}
    code = (
        HistoricalApprovalReasonCode.OUT_OF_SAMPLE_EVIDENCE_INSUFFICIENT
        if attachment.status in insufficient_statuses
        else HistoricalApprovalReasonCode.OUT_OF_SAMPLE_EVIDENCE_FAILED
    )
    return (
        HistoricalApprovalReason(
            code=code,
            message=(
                f"Historical validation status {attachment.status} cannot advance "
                "strategy eligibility."
            ),
        ),
    )
