"""Deterministic binding between verified provider limits and an active account policy."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from apex.domain import AccountPolicy, AccountPolicyType
from apex.funded.provider_limits_registry import DrawdownModel, FundedProviderLimitPreset

__all__ = ["ProviderPolicyBinding", "bind_provider_policy"]


class ProviderPolicyBinding(BaseModel):
    """Path-independent, explicitly non-authorizing provider-policy decision snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str
    provider_name: str
    challenge_phase: str
    preset_sha256: str
    verification_date: date
    drawdown_model: DrawdownModel
    weekend_trading_allowed: bool
    overnight_holding_allowed: bool
    news_trading_allowed: bool
    compatible: bool
    compatibility_reasons: tuple[str, ...] = ()
    execution_authorized: bool = False


def bind_provider_policy(
    preset: FundedProviderLimitPreset,
    policy: AccountPolicy,
    *,
    as_of: date,
    maximum_age_days: int,
) -> ProviderPolicyBinding:
    """Build a stable compatibility snapshot without authorizing execution."""

    reasons: list[str] = []
    if policy.type is not AccountPolicyType.FUNDED:
        reasons.append("FUNDED_POLICY_REQUIRED")
    if policy.provider_name is not None and (
        policy.provider_name.strip().casefold() != preset.provider_name.strip().casefold()
    ):
        reasons.append("PROVIDER_POLICY_MISMATCH")
    if policy.challenge_phase is not None and (
        policy.challenge_phase.strip().casefold() != preset.challenge_phase.strip().casefold()
    ):
        reasons.append("CHALLENGE_PHASE_MISMATCH")
    preset_sha256 = preset.preset_sha256 or preset.content_sha256
    if policy.provider_preset_sha256 is not None and policy.provider_preset_sha256 != preset_sha256:
        reasons.append("PROVIDER_PRESET_MISMATCH")
    if not preset.limits_verified:
        reasons.append("PROVIDER_LIMITS_UNVERIFIED")
    if not preset.is_fresh(as_of=as_of, maximum_age_days=maximum_age_days):
        reasons.append("PROVIDER_LIMITS_STALE")
    if policy.external_daily_drawdown_limit_pct != preset.external_daily_drawdown_limit_pct:
        reasons.append("DAILY_DRAWDOWN_LIMIT_MISMATCH")
    if policy.external_total_drawdown_limit_pct != preset.external_total_drawdown_limit_pct:
        reasons.append("TOTAL_DRAWDOWN_LIMIT_MISMATCH")
    if policy.maximum_trades_per_day > preset.maximum_trades_per_day:
        reasons.append("MAXIMUM_TRADES_MISMATCH")
    if policy.weekend_trading_allowed and not preset.weekend_trading_allowed:
        reasons.append("WEEKEND_PERMISSION_MISMATCH")
    if policy.overnight_holding_allowed and not preset.overnight_holding_allowed:
        reasons.append("OVERNIGHT_PERMISSION_MISMATCH")
    if policy.news_trading_allowed and not preset.news_trading_allowed:
        reasons.append("NEWS_PERMISSION_MISMATCH")

    unique_reasons = tuple(dict.fromkeys(reasons))
    return ProviderPolicyBinding(
        provider_id=preset.provider_id,
        provider_name=preset.provider_name,
        challenge_phase=preset.challenge_phase,
        preset_sha256=preset_sha256,
        verification_date=preset.verified_on,
        drawdown_model=preset.drawdown_model,
        weekend_trading_allowed=preset.weekend_trading_allowed,
        overnight_holding_allowed=preset.overnight_holding_allowed,
        news_trading_allowed=preset.news_trading_allowed,
        compatible=not unique_reasons,
        compatibility_reasons=unique_reasons,
        execution_authorized=False,
    )