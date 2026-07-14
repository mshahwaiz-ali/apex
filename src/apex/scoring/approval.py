"""Deterministic N3 futures strategy approval and eligibility decisions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.config.strategy_approval import StrategyApprovalConfig, StrategyQualityClass
from apex.domain import AccountPolicyDecision, EntryState, RiskMode
from apex.strategies import StrategyType


class SetupEligibility(StrEnum):
    """Operational eligibility after strategy, risk-mode, and policy checks."""

    FUNDED_ELIGIBLE = "FUNDED_ELIGIBLE"
    PAPER_ONLY = "PAPER_ONLY"
    EXPERIMENTAL_ONLY = "EXPERIMENTAL_ONLY"
    REJECTED = "REJECTED"


class ApprovalReasonCode(StrEnum):
    """Stable machine-readable N3 approval and rejection reasons."""

    STRATEGY_APPROVED = "STRATEGY_APPROVED"
    STRATEGY_SCORE_BELOW_MODE_THRESHOLD = "STRATEGY_SCORE_BELOW_MODE_THRESHOLD"
    STANDARD_MODE_STRATEGY_RESTRICTED = "STANDARD_MODE_STRATEGY_RESTRICTED"
    ENTRY_STATE_NOT_ACTIONABLE = "ENTRY_STATE_NOT_ACTIONABLE"
    ACCOUNT_POLICY_LOCKED = "ACCOUNT_POLICY_LOCKED"
    HISTORICAL_EVIDENCE_INSUFFICIENT = "HISTORICAL_EVIDENCE_INSUFFICIENT"
    FORWARD_PAPER_EVIDENCE_REQUIRED = "FORWARD_PAPER_EVIDENCE_REQUIRED"
    AGGRESSIVE_MODE_PAPER_ONLY = "AGGRESSIVE_MODE_PAPER_ONLY"
    EXTREME_MODE_EXPERIMENTAL_ONLY = "EXTREME_MODE_EXPERIMENTAL_ONLY"


@dataclass(frozen=True, slots=True)
class ApprovalReason:
    """One ordered, serializable explanation for an approval decision."""

    code: ApprovalReasonCode
    message: str

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("approval reason message cannot be empty")

    def to_payload(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message}


@dataclass(frozen=True, slots=True)
class StrategyApprovalDecision:
    """Complete deterministic quality and operational eligibility result."""

    approved: bool
    eligibility: SetupEligibility
    strategy: StrategyType
    risk_mode: RiskMode
    quality_class: StrategyQualityClass
    actual_score: float
    required_score: float
    reasons: tuple[ApprovalReason, ...]

    def __post_init__(self) -> None:
        for label, value in (
            ("actual score", self.actual_score),
            ("required score", self.required_score),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 100.0:
                raise ValueError(f"{label} must be finite and between zero and 100")
        if not self.reasons:
            raise ValueError("strategy approval decision requires at least one reason")
        if self.approved is (self.eligibility is SetupEligibility.REJECTED):
            raise ValueError("approved state must agree with setup eligibility")

    def to_payload(self) -> dict[str, object]:
        return {
            "approved": self.approved,
            "eligibility": self.eligibility.value,
            "strategy": self.strategy.value,
            "risk_mode": self.risk_mode.value,
            "quality_class": self.quality_class.value,
            "actual_score": self.actual_score,
            "required_score": self.required_score,
            "reasons": [reason.to_payload() for reason in self.reasons],
        }


_NON_ACTIONABLE_ENTRY_STATES = {
    EntryState.MISSED_ENTRY,
    EntryState.INVALIDATED,
    EntryState.NO_TRADE,
}


def evaluate_strategy_approval(
    *,
    strategy: StrategyType,
    risk_mode: RiskMode,
    score: float,
    entry_state: EntryState,
    config: StrategyApprovalConfig,
    account_policy_decision: AccountPolicyDecision | None = None,
    historical_evidence_available: bool = False,
) -> StrategyApprovalDecision:
    """Evaluate N3 quality and eligibility without fabricating historical evidence."""

    rule = config.rule_for(strategy)
    required_score = rule.minimum_score_for(risk_mode)
    reasons: list[ApprovalReason] = []

    if not math.isfinite(score) or not 0.0 <= score <= 100.0:
        raise ValueError("strategy approval score must be finite and between zero and 100")

    if score < required_score:
        reasons.append(
            ApprovalReason(
                code=ApprovalReasonCode.STRATEGY_SCORE_BELOW_MODE_THRESHOLD,
                message=(
                    f"{strategy.value} scored {score:.2f} but {risk_mode.value} "
                    f"requires {required_score:.2f}."
                ),
            )
        )

    if entry_state in _NON_ACTIONABLE_ENTRY_STATES:
        reasons.append(
            ApprovalReason(
                code=ApprovalReasonCode.ENTRY_STATE_NOT_ACTIONABLE,
                message=f"Entry state {entry_state.value} is not actionable.",
            )
        )

    if account_policy_decision is not None and not account_policy_decision.approved:
        labels = ", ".join(reason.value for reason in account_policy_decision.lockout_reasons)
        reasons.append(
            ApprovalReason(
                code=ApprovalReasonCode.ACCOUNT_POLICY_LOCKED,
                message=f"Account policy rejected the setup: {labels}.",
            )
        )

    hard_rejection_codes = {
        ApprovalReasonCode.STRATEGY_SCORE_BELOW_MODE_THRESHOLD,
        ApprovalReasonCode.ENTRY_STATE_NOT_ACTIONABLE,
        ApprovalReasonCode.ACCOUNT_POLICY_LOCKED,
    }
    if any(reason.code in hard_rejection_codes for reason in reasons):
        return StrategyApprovalDecision(
            approved=False,
            eligibility=SetupEligibility.REJECTED,
            strategy=strategy,
            risk_mode=risk_mode,
            quality_class=rule.quality_class,
            actual_score=score,
            required_score=required_score,
            reasons=tuple(reasons),
        )

    reasons.append(
        ApprovalReason(
            code=ApprovalReasonCode.STRATEGY_APPROVED,
            message=(
                f"{strategy.value} clears the {risk_mode.value} threshold of {required_score:.2f}."
            ),
        )
    )

    if risk_mode is RiskMode.EXTREME:
        eligibility = SetupEligibility.EXPERIMENTAL_ONLY
        reasons.append(
            ApprovalReason(
                code=ApprovalReasonCode.EXTREME_MODE_EXPERIMENTAL_ONLY,
                message="EXTREME mode remains restricted to experimental use.",
            )
        )
    elif risk_mode is RiskMode.AGGRESSIVE:
        eligibility = SetupEligibility.PAPER_ONLY
        reasons.append(
            ApprovalReason(
                code=ApprovalReasonCode.AGGRESSIVE_MODE_PAPER_ONLY,
                message="AGGRESSIVE mode remains paper-only until validation is complete.",
            )
        )
    elif not historical_evidence_available:
        eligibility = SetupEligibility.PAPER_ONLY
        reasons.append(
            ApprovalReason(
                code=ApprovalReasonCode.HISTORICAL_EVIDENCE_INSUFFICIENT,
                message="No validated setup-specific historical edge is available yet.",
            )
        )
    else:
        eligibility = SetupEligibility.PAPER_ONLY
        reasons.append(
            ApprovalReason(
                code=ApprovalReasonCode.FORWARD_PAPER_EVIDENCE_REQUIRED,
                message="Historical evidence alone cannot advance beyond paper-only eligibility.",
            )
        )

    if risk_mode is RiskMode.STANDARD and rule.quality_class is StrategyQualityClass.RESTRICTED:
        reasons.append(
            ApprovalReason(
                code=ApprovalReasonCode.STANDARD_MODE_STRATEGY_RESTRICTED,
                message=(
                    f"{strategy.value} is a restricted STANDARD-mode strategy and "
                    "required its higher configured threshold."
                ),
            )
        )

    return StrategyApprovalDecision(
        approved=True,
        eligibility=eligibility,
        strategy=strategy,
        risk_mode=risk_mode,
        quality_class=rule.quality_class,
        actual_score=score,
        required_score=required_score,
        reasons=tuple(reasons),
    )
