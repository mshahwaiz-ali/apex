"""Deterministic funded-account readiness contracts and evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from apex.domain import AccountPolicyDecision, AccountPolicyType, RiskMode
from apex.execution.contracts import KillSwitchState

if TYPE_CHECKING:
    from apex.validation import AggregateHistoryReport, ForwardValidationReport


class FundedReadinessReason(StrEnum):
    """Stable machine-readable R1 blocker codes."""

    PROVIDER_LIMITS_UNVERIFIED = "PROVIDER_LIMITS_UNVERIFIED"
    FORWARD_VALIDATION_INCOMPLETE = "FORWARD_VALIDATION_INCOMPLETE"
    STANDARD_MODE_REQUIRED = "STANDARD_MODE_REQUIRED"
    FUNDED_POLICY_REQUIRED = "FUNDED_POLICY_REQUIRED"
    ACCOUNT_POLICY_BLOCKED = "ACCOUNT_POLICY_BLOCKED"
    DAILY_LOCKOUT_VERIFICATION_FAILED = "DAILY_LOCKOUT_VERIFICATION_FAILED"
    TOTAL_BUFFER_VERIFICATION_FAILED = "TOTAL_BUFFER_VERIFICATION_FAILED"
    PRE_TRADE_CHECKLIST_INCOMPLETE = "PRE_TRADE_CHECKLIST_INCOMPLETE"
    POST_TRADE_CHECKLIST_INCOMPLETE = "POST_TRADE_CHECKLIST_INCOMPLETE"
    KILL_SWITCH_NOT_ENABLED = "KILL_SWITCH_NOT_ENABLED"


@dataclass(frozen=True, slots=True)
class FundedProviderLimits:
    """Date-stamped provider limits supplied from a verified external source."""

    provider_name: str
    verified_on: date
    external_daily_drawdown_limit_pct: float
    external_total_drawdown_limit_pct: float
    maximum_trades_per_day: int
    limits_verified: bool

    def __post_init__(self) -> None:
        if not self.provider_name.strip():
            raise ValueError("funded provider name cannot be empty")
        for name in (
            "external_daily_drawdown_limit_pct",
            "external_total_drawdown_limit_pct",
        ):
            value = getattr(self, name)
            if not 0.0 < value <= 100.0:
                raise ValueError(f"{name.replace('_', ' ')} must be between zero and 100")
        if self.maximum_trades_per_day < 1:
            raise ValueError("maximum trades per day must be positive")


@dataclass(frozen=True, slots=True)
class ManualExecutionChecklist:
    """Required manual pre-trade or post-trade audit confirmations."""

    analysis_reviewed: bool
    risk_reviewed: bool
    account_state_reviewed: bool
    order_or_fill_verified: bool
    lifecycle_recorded: bool

    @property
    def complete(self) -> bool:
        return all(
            (
                self.analysis_reviewed,
                self.risk_reviewed,
                self.account_state_reviewed,
                self.order_or_fill_verified,
                self.lifecycle_recorded,
            )
        )


@dataclass(frozen=True, slots=True)
class FundedReadinessReport:
    """Schema-versioned R1 readiness decision for manual funded operation."""

    schema_version: int
    generated_at: datetime
    ready: bool
    provider_name: str
    reasons: tuple[FundedReadinessReason, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported funded-readiness schema version")
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("funded-readiness report time must be timezone-aware")
        if not self.provider_name.strip():
            raise ValueError("funded-readiness provider name cannot be empty")
        if self.ready and self.reasons:
            raise ValueError("ready funded report cannot contain blockers")


def evaluate_funded_readiness(
    *,
    provider_limits: FundedProviderLimits,
    forward_validation: ForwardValidationReport | AggregateHistoryReport,
    risk_mode: RiskMode,
    account_policy_type: AccountPolicyType,
    account_policy_decision: AccountPolicyDecision,
    daily_lockout_verified: bool,
    total_buffer_verified: bool,
    pre_trade_checklist: ManualExecutionChecklist,
    post_trade_checklist: ManualExecutionChecklist,
    kill_switch_state: KillSwitchState,
    generated_at: datetime,
) -> FundedReadinessReport:
    """Evaluate R1 readiness, preferring aggregate P1 history while retaining legacy input."""

    from apex.validation import AggregateHistoryReport, ProductionEligibility

    reasons: list[FundedReadinessReason] = []
    if not provider_limits.limits_verified:
        reasons.append(FundedReadinessReason.PROVIDER_LIMITS_UNVERIFIED)
    validation_ready = (
        forward_validation.ready_for_funded_review
        if isinstance(forward_validation, AggregateHistoryReport)
        else forward_validation.eligibility is ProductionEligibility.READY_FOR_FUNDED_REVIEW
    )
    if not validation_ready:
        reasons.append(FundedReadinessReason.FORWARD_VALIDATION_INCOMPLETE)
    if risk_mode is not RiskMode.STANDARD:
        reasons.append(FundedReadinessReason.STANDARD_MODE_REQUIRED)
    if account_policy_type is not AccountPolicyType.FUNDED:
        reasons.append(FundedReadinessReason.FUNDED_POLICY_REQUIRED)
    if not account_policy_decision.approved:
        reasons.append(FundedReadinessReason.ACCOUNT_POLICY_BLOCKED)
    if not daily_lockout_verified:
        reasons.append(FundedReadinessReason.DAILY_LOCKOUT_VERIFICATION_FAILED)
    if not total_buffer_verified:
        reasons.append(FundedReadinessReason.TOTAL_BUFFER_VERIFICATION_FAILED)
    if not pre_trade_checklist.complete:
        reasons.append(FundedReadinessReason.PRE_TRADE_CHECKLIST_INCOMPLETE)
    if not post_trade_checklist.complete:
        reasons.append(FundedReadinessReason.POST_TRADE_CHECKLIST_INCOMPLETE)
    if kill_switch_state is not KillSwitchState.ENABLED:
        reasons.append(FundedReadinessReason.KILL_SWITCH_NOT_ENABLED)

    unique_reasons = tuple(dict.fromkeys(reasons))
    return FundedReadinessReport(
        schema_version=1,
        generated_at=generated_at,
        ready=not unique_reasons,
        provider_name=provider_limits.provider_name,
        reasons=unique_reasons,
    )
