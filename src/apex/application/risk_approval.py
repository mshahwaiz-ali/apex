"""Combine risk-mode limits and account-policy permissions for futures plans."""

from __future__ import annotations

from apex.application.futures_plan import (
    FuturesPlanSafetyError,
    build_futures_plan as _build_futures_plan,
)
from apex.config import FuturesProductConfig, load_futures_product_config
from apex.domain import (
    AccountPolicy,
    AccountPolicyDecision,
    AccountPolicyState,
    FuturesAccountInput,
    evaluate_account_policy,
)
from apex.risk.contracts import RiskApprovedSetup


def build_futures_plan(
    setup: RiskApprovedSetup,
    account: FuturesAccountInput,
    *,
    product_config: FuturesProductConfig | None = None,
    account_policy: AccountPolicy | None = None,
    account_policy_state: AccountPolicyState | None = None,
) -> dict[str, object]:
    """Build a futures plan after independent mode and account-policy checks."""

    config = product_config or load_futures_product_config("config/futures.yaml")
    defaults = config.defaults_for(account.risk_mode)
    mode_reasons = _risk_mode_rejection_reasons(account, defaults, account_policy_state)
    if mode_reasons:
        raise FuturesPlanSafetyError(mode_reasons)

    policy_decision = _evaluate_policy(account, account_policy, account_policy_state)
    if policy_decision is not None and not policy_decision.approved:
        reasons = tuple(f"account policy lockout: {reason.value}" for reason in policy_decision.lockout_reasons)
        raise FuturesPlanSafetyError(reasons)

    plan = _build_futures_plan(setup, account, product_config=config)
    plan["risk_mode"] = account.risk_mode.value
    plan["risk_mode_config"] = defaults.model_dump(mode="json")
    plan["account_policy"] = (
        account_policy.model_dump(mode="json") if account_policy is not None else None
    )
    plan["account_policy_decision"] = (
        policy_decision.model_dump(mode="json") if policy_decision is not None else None
    )
    return plan


def build_futures_plan_result(
    setup: RiskApprovedSetup,
    account: FuturesAccountInput,
    *,
    product_config: FuturesProductConfig | None = None,
    account_policy: AccountPolicy | None = None,
    account_policy_state: AccountPolicyState | None = None,
) -> dict[str, object]:
    """Return an approved or rejected policy-aware futures-plan payload."""

    try:
        return build_futures_plan(
            setup,
            account,
            product_config=product_config,
            account_policy=account_policy,
            account_policy_state=account_policy_state,
        )
    except FuturesPlanSafetyError as exc:
        return {
            "status": "REJECTED",
            "risk_mode": account.risk_mode.value,
            "reasons": list(exc.reasons),
        }


def _evaluate_policy(
    account: FuturesAccountInput,
    policy: AccountPolicy | None,
    state: AccountPolicyState | None,
) -> AccountPolicyDecision | None:
    if policy is None and state is None:
        return None
    if policy is None or state is None:
        raise FuturesPlanSafetyError(
            ("account policy and account policy state must be supplied together",)
        )
    proposed_state = state.model_copy(
        update={
            "proposed_risk_pct": account.maximum_account_loss_percentage,
            "proposed_has_stop_loss": True,
        }
    )
    return evaluate_account_policy(policy, proposed_state)


def _risk_mode_rejection_reasons(
    account: FuturesAccountInput,
    defaults: object,
    state: AccountPolicyState | None,
) -> tuple[str, ...]:
    account_loss_percentage = getattr(defaults, "account_loss_percentage")
    maximum_open_risk_percentage = getattr(defaults, "maximum_open_risk_percentage")
    maximum_daily_loss_percentage = getattr(defaults, "maximum_daily_loss_percentage")
    maximum_consecutive_losses = getattr(defaults, "maximum_consecutive_losses")
    reasons: list[str] = []
    if account.maximum_account_loss_percentage > account_loss_percentage:
        reasons.append(
            f"account loss {account.maximum_account_loss_percentage:.2f}% exceeds "
            f"{account.risk_mode.value} mode limit {account_loss_percentage:.2f}%"
        )
    if state is not None:
        daily_drawdown = max(
            0.0,
            (state.start_of_day_equity - state.current_equity)
            / state.start_of_day_equity
            * 100.0,
        )
        if daily_drawdown >= maximum_daily_loss_percentage:
            reasons.append(
                f"daily drawdown {daily_drawdown:.2f}% reached "
                f"{account.risk_mode.value} mode limit {maximum_daily_loss_percentage:.2f}%"
            )
        if state.consecutive_losses >= maximum_consecutive_losses:
            reasons.append(
                f"consecutive losses {state.consecutive_losses} reached "
                f"{account.risk_mode.value} mode limit {maximum_consecutive_losses}"
            )
        projected_open_risk = state.total_open_risk_pct + account.maximum_account_loss_percentage
        if projected_open_risk > maximum_open_risk_percentage:
            reasons.append(
                f"projected open risk {projected_open_risk:.2f}% exceeds "
                f"{account.risk_mode.value} mode limit {maximum_open_risk_percentage:.2f}%"
            )
    return tuple(reasons)
