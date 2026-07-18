"""Derive canonical setup maturity from legacy candidate actionability."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.application.methodology_strategy_contracts import (
    ConfirmationPolicy,
    SetupMaturity,
)
from apex.application.methodology_strategy_registry import strategy_eligibility
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


class PublicEntryState(StrEnum):
    WAIT_CLOSE = "WAIT_CLOSE"
    WAIT_BREAK = "WAIT_BREAK"
    WAIT_RETEST = "WAIT_RETEST"
    WAIT_RECLAIM = "WAIT_RECLAIM"
    AVAILABLE = "AVAILABLE"
    AGGRESSIVE = "AGGRESSIVE"
    LATE = "LATE"
    MISSED = "MISSED"
    EXPIRED = "EXPIRED"
    CANCELED = "CANCELED"
    FAILED = "FAILED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True, slots=True)
class SetupMaturityAssessment:
    strategy: StrategyType
    legacy_status: EntryStatus
    maturity: SetupMaturity
    confirmation_policy: ConfirmationPolicy
    execution_conditions_complete: bool
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.reason_codes or not self.reasons:
            raise ValueError("setup maturity assessment requires reasons")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("setup maturity reason codes must be unique")

    @property
    def public_entry_state(self) -> PublicEntryState:
        if self.maturity is SetupMaturity.INVALIDATED:
            return PublicEntryState.INVALIDATED
        if self.maturity is SetupMaturity.ENTRY_LATE:
            return PublicEntryState.LATE
        if self.maturity is SetupMaturity.ENTRY_MISSED:
            return PublicEntryState.MISSED
        if self.maturity is SetupMaturity.PATTERN_FAILED:
            return PublicEntryState.FAILED
        if self.maturity is SetupMaturity.RETEST_PENDING:
            return PublicEntryState.WAIT_RETEST
        if self.maturity is SetupMaturity.RECLAIM_PENDING:
            return PublicEntryState.WAIT_RECLAIM
        if self.maturity in {
            SetupMaturity.CONFIRMATION_PENDING_CLOSE,
            SetupMaturity.TRIGGER_PROVISIONAL,
        }:
            return PublicEntryState.WAIT_CLOSE
        if self.maturity is SetupMaturity.ENTRY_AVAILABLE:
            return (
                PublicEntryState.AGGRESSIVE
                if self.legacy_status is EntryStatus.AGGRESSIVE_NOW
                else PublicEntryState.AVAILABLE
            )
        return PublicEntryState.WAIT_BREAK


def derive_setup_maturity(
    strategy: StrategyType,
    legacy_status: EntryStatus,
) -> SetupMaturityAssessment:
    """Map legacy actionability into strategy-specific canonical maturity.

    The bridge is intentionally conservative. A legacy READY_NOW state does not
    complete a strategy whose registry policy still requires a close, retest, or
    reclaim. This module is diagnostic only and does not alter selection yet.
    """

    policy = strategy_eligibility(strategy).confirmation_policy

    if legacy_status is EntryStatus.INVALIDATED:
        return _assessment(
            strategy,
            legacy_status,
            SetupMaturity.INVALIDATED,
            policy,
            complete=False,
            code="METHODOLOGY_SETUP_INVALIDATED",
            reason="the legacy candidate is already invalidated",
        )
    if legacy_status is EntryStatus.LATE_OR_CHASING:
        return _assessment(
            strategy,
            legacy_status,
            SetupMaturity.ENTRY_LATE,
            policy,
            complete=False,
            code="METHODOLOGY_ENTRY_LATE",
            reason="the legacy candidate is late or requires chasing",
        )
    if legacy_status is EntryStatus.WATCH_NEAR_ENTRY:
        return _assessment(
            strategy,
            legacy_status,
            SetupMaturity.PATTERN_DEVELOPING,
            policy,
            complete=False,
            code="METHODOLOGY_PATTERN_DEVELOPING",
            reason="price is near the opportunity but execution conditions are incomplete",
        )
    if legacy_status is EntryStatus.PULLBACK_PREFERRED:
        maturity = _pending_maturity(policy, fallback=SetupMaturity.PATTERN_DEVELOPING)
        return _assessment(
            strategy,
            legacy_status,
            maturity,
            policy,
            complete=False,
            code="METHODOLOGY_BETTER_ENTRY_PENDING",
            reason="a preferred nearby entry or strategy-specific confirmation remains pending",
        )
    if legacy_status is EntryStatus.AGGRESSIVE_NOW:
        if policy is ConfirmationPolicy.INTRABAR_ALLOWED:
            return _assessment(
                strategy,
                legacy_status,
                SetupMaturity.ENTRY_AVAILABLE,
                policy,
                complete=True,
                code="METHODOLOGY_INTRABAR_ENTRY_AVAILABLE",
                reason=(
                    "the strategy permits intrabar execution and the aggressive entry is available"
                ),
            )
        return _assessment(
            strategy,
            legacy_status,
            SetupMaturity.TRIGGER_PROVISIONAL,
            policy,
            complete=False,
            code="METHODOLOGY_AGGRESSIVE_TRIGGER_PROVISIONAL",
            reason=(
                "the aggressive legacy trigger is provisional under this strategy "
                "confirmation policy"
            ),
        )

    if policy in {
        ConfirmationPolicy.INTRABAR_ALLOWED,
        ConfirmationPolicy.LOWER_TIMEFRAME_CONFIRMATION_ALLOWED,
        ConfirmationPolicy.MIXED,
    }:
        return _assessment(
            strategy,
            legacy_status,
            SetupMaturity.ENTRY_AVAILABLE,
            policy,
            complete=True,
            code="METHODOLOGY_ENTRY_AVAILABLE",
            reason="legacy readiness is compatible with the strategy confirmation policy",
        )

    maturity = _pending_maturity(policy, fallback=SetupMaturity.TRIGGER_PROVISIONAL)
    return _assessment(
        strategy,
        legacy_status,
        maturity,
        policy,
        complete=False,
        code="METHODOLOGY_CONFIRMATION_STILL_REQUIRED",
        reason=f"legacy readiness does not satisfy the {policy.value} policy",
    )


def setup_maturity_payload(assessment: SetupMaturityAssessment) -> dict[str, object]:
    return {
        "strategy": assessment.strategy.value,
        "legacy_status": assessment.legacy_status.value,
        "maturity": assessment.maturity.value,
        "entry_state": assessment.public_entry_state.value,
        "confirmation_policy": assessment.confirmation_policy.value,
        "execution_conditions_complete": assessment.execution_conditions_complete,
        "reason_codes": list(assessment.reason_codes),
        "reasons": list(assessment.reasons),
    }


def _pending_maturity(
    policy: ConfirmationPolicy,
    *,
    fallback: SetupMaturity,
) -> SetupMaturity:
    if policy is ConfirmationPolicy.CLOSE_REQUIRED:
        return SetupMaturity.CONFIRMATION_PENDING_CLOSE
    if policy is ConfirmationPolicy.RETEST_REQUIRED:
        return SetupMaturity.RETEST_PENDING
    if policy is ConfirmationPolicy.RECLAIM_REQUIRED:
        return SetupMaturity.RECLAIM_PENDING
    return fallback


def _assessment(
    strategy: StrategyType,
    legacy_status: EntryStatus,
    maturity: SetupMaturity,
    policy: ConfirmationPolicy,
    *,
    complete: bool,
    code: str,
    reason: str,
) -> SetupMaturityAssessment:
    return SetupMaturityAssessment(
        strategy=strategy,
        legacy_status=legacy_status,
        maturity=maturity,
        confirmation_policy=policy,
        execution_conditions_complete=complete,
        reason_codes=(code,),
        reasons=(reason,),
    )


__all__ = [
    "PublicEntryState",
    "SetupMaturityAssessment",
    "derive_setup_maturity",
    "setup_maturity_payload",
]
