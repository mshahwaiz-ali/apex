"""Account-policy contracts kept separate from trading risk modes."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AccountPolicyType(StrEnum):
    """Supported account-policy families."""

    PERSONAL = "PERSONAL"
    FUNDED = "FUNDED"
    PAPER = "PAPER"


class AccountLockoutReason(StrEnum):
    """Deterministic reasons that prevent approval of another trade."""

    DAILY_DRAWDOWN = "DAILY_DRAWDOWN"
    TOTAL_DRAWDOWN = "TOTAL_DRAWDOWN"
    MAXIMUM_TRADES = "MAXIMUM_TRADES"
    CONSECUTIVE_LOSSES = "CONSECUTIVE_LOSSES"
    MAXIMUM_OPEN_RISK = "MAXIMUM_OPEN_RISK"
    MAXIMUM_DIRECTIONAL_EXPOSURE = "MAXIMUM_DIRECTIONAL_EXPOSURE"
    MAXIMUM_CORRELATED_EXPOSURE = "MAXIMUM_CORRELATED_EXPOSURE"
    WEEKEND_RESTRICTED = "WEEKEND_RESTRICTED"
    SESSION_RESTRICTED = "SESSION_RESTRICTED"
    STOP_LOSS_REQUIRED = "STOP_LOSS_REQUIRED"


class AccountPolicy(BaseModel):
    """Configurable account permissions independent of strategy aggressiveness."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: AccountPolicyType
    provider_name: str | None = None
    challenge_phase: str | None = None
    initial_balance: float = Field(gt=0)
    external_daily_drawdown_limit_pct: float = Field(gt=0, le=100)
    external_total_drawdown_limit_pct: float = Field(gt=0, le=100)
    internal_daily_stop_pct: float = Field(gt=0, le=100)
    internal_total_drawdown_buffer_pct: float = Field(ge=0, le=100)
    maximum_risk_per_trade_pct: float = Field(gt=0, le=100)
    maximum_total_open_risk_pct: float = Field(gt=0, le=100)
    maximum_directional_exposure_pct: float = Field(gt=0, le=100)
    maximum_correlated_exposure_pct: float = Field(gt=0, le=100)
    maximum_trades_per_day: int = Field(gt=0)
    maximum_consecutive_losses: int = Field(gt=0)
    required_stop_loss: bool = True
    weekend_trading_allowed: bool = True
    allowed_sessions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_drawdown_geometry(self) -> Self:
        if self.internal_daily_stop_pct > self.external_daily_drawdown_limit_pct:
            raise ValueError("internal daily stop cannot exceed external daily drawdown limit")
        if self.internal_total_drawdown_buffer_pct >= self.external_total_drawdown_limit_pct:
            raise ValueError("internal total-drawdown buffer must remain below the external limit")
        if self.maximum_risk_per_trade_pct > self.maximum_total_open_risk_pct:
            raise ValueError("maximum risk per trade cannot exceed maximum total open risk")
        if len(self.allowed_sessions) != len(set(self.allowed_sessions)):
            raise ValueError("allowed account-policy sessions must be unique")
        return self

    @property
    def internal_total_stop_pct(self) -> float:
        """Return the internal lockout threshold before the external total limit."""

        return self.external_total_drawdown_limit_pct - self.internal_total_drawdown_buffer_pct


class AccountPolicyState(BaseModel):
    """Current account state evaluated before approving a setup."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    current_balance: float = Field(gt=0)
    current_equity: float = Field(gt=0)
    start_of_day_equity: float = Field(gt=0)
    trades_today: int = Field(ge=0)
    consecutive_losses: int = Field(ge=0)
    total_open_risk_pct: float = Field(ge=0, le=100)
    directional_exposure_pct: float = Field(ge=0, le=100)
    correlated_exposure_pct: float = Field(ge=0, le=100)
    is_weekend: bool = False
    session: str | None = None
    proposed_risk_pct: float = Field(ge=0, le=100)
    proposed_directional_exposure_pct: float = Field(default=0.0, ge=0, le=100)
    proposed_correlated_exposure_pct: float = Field(default=0.0, ge=0, le=100)
    proposed_has_stop_loss: bool = True

    @model_validator(mode="after")
    def validate_proposed_exposure_geometry(self) -> Self:
        if self.proposed_directional_exposure_pct > self.proposed_risk_pct:
            raise ValueError("proposed directional exposure cannot exceed proposed risk")
        if self.proposed_correlated_exposure_pct > self.proposed_risk_pct:
            raise ValueError("proposed correlated exposure cannot exceed proposed risk")
        return self


class AccountPolicyDecision(BaseModel):
    """Serializable account-policy approval result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    approved: bool
    lockout_reasons: tuple[AccountLockoutReason, ...] = ()
    daily_drawdown_pct: float = Field(ge=0)
    total_drawdown_pct: float = Field(ge=0)
    projected_total_open_risk_pct: float = Field(default=0.0, ge=0)
    projected_directional_exposure_pct: float = Field(default=0.0, ge=0)
    projected_correlated_exposure_pct: float = Field(default=0.0, ge=0)


def evaluate_account_policy(
    policy: AccountPolicy,
    state: AccountPolicyState,
) -> AccountPolicyDecision:
    """Evaluate account restrictions without modifying risk-mode behavior."""

    daily_drawdown_pct = max(
        0.0,
        (state.start_of_day_equity - state.current_equity) / state.start_of_day_equity * 100.0,
    )
    total_drawdown_pct = max(
        0.0,
        (policy.initial_balance - state.current_equity) / policy.initial_balance * 100.0,
    )
    projected_total_open_risk_pct = state.total_open_risk_pct + state.proposed_risk_pct
    projected_directional_exposure_pct = (
        state.directional_exposure_pct + state.proposed_directional_exposure_pct
    )
    projected_correlated_exposure_pct = (
        state.correlated_exposure_pct + state.proposed_correlated_exposure_pct
    )
    reasons: list[AccountLockoutReason] = []

    if daily_drawdown_pct >= policy.internal_daily_stop_pct:
        reasons.append(AccountLockoutReason.DAILY_DRAWDOWN)
    if total_drawdown_pct >= policy.internal_total_stop_pct:
        reasons.append(AccountLockoutReason.TOTAL_DRAWDOWN)
    if state.trades_today >= policy.maximum_trades_per_day:
        reasons.append(AccountLockoutReason.MAXIMUM_TRADES)
    if state.consecutive_losses >= policy.maximum_consecutive_losses:
        reasons.append(AccountLockoutReason.CONSECUTIVE_LOSSES)
    if state.proposed_risk_pct > policy.maximum_risk_per_trade_pct:
        reasons.append(AccountLockoutReason.MAXIMUM_OPEN_RISK)
    if projected_total_open_risk_pct > policy.maximum_total_open_risk_pct:
        reasons.append(AccountLockoutReason.MAXIMUM_OPEN_RISK)
    if projected_directional_exposure_pct > policy.maximum_directional_exposure_pct:
        reasons.append(AccountLockoutReason.MAXIMUM_DIRECTIONAL_EXPOSURE)
    if projected_correlated_exposure_pct > policy.maximum_correlated_exposure_pct:
        reasons.append(AccountLockoutReason.MAXIMUM_CORRELATED_EXPOSURE)
    if state.is_weekend and not policy.weekend_trading_allowed:
        reasons.append(AccountLockoutReason.WEEKEND_RESTRICTED)
    if policy.allowed_sessions and state.session not in policy.allowed_sessions:
        reasons.append(AccountLockoutReason.SESSION_RESTRICTED)
    if policy.required_stop_loss and not state.proposed_has_stop_loss:
        reasons.append(AccountLockoutReason.STOP_LOSS_REQUIRED)

    unique_reasons = tuple(dict.fromkeys(reasons))
    return AccountPolicyDecision(
        approved=not unique_reasons,
        lockout_reasons=unique_reasons,
        daily_drawdown_pct=daily_drawdown_pct,
        total_drawdown_pct=total_drawdown_pct,
        projected_total_open_risk_pct=projected_total_open_risk_pct,
        projected_directional_exposure_pct=projected_directional_exposure_pct,
        projected_correlated_exposure_pct=projected_correlated_exposure_pct,
    )
