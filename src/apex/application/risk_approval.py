"""Combine strategy quality, risk-mode limits, and account-policy permissions."""

from __future__ import annotations

from pathlib import Path

from apex.application.futures_plan import (
    FuturesPlanSafetyError as FuturesPlanSafetyError,
)
from apex.application.futures_plan import build_futures_plan as _build_futures_plan
from apex.application.trade_management import build_trade_management_plan
from apex.config import (
    FuturesProductConfig,
    RiskModeDefaults,
    StrategyApprovalConfig,
    load_futures_product_config,
    load_strategy_approval_config,
)
from apex.domain import (
    AccountPolicy,
    AccountPolicyDecision,
    AccountPolicyState,
    EntryPlan,
    FuturesAccountInput,
    FuturesDirection,
    PositionPlan,
    TargetPlan,
    evaluate_account_policy,
)
from apex.risk.contracts import RiskApprovedSetup
from apex.scoring.approval import StrategyApprovalDecision, evaluate_strategy_approval

DEFAULT_STRATEGY_APPROVAL_CONFIG_PATH = Path("config/strategy_approval.yaml")


class StrategyApprovalError(FuturesPlanSafetyError):
    """Raised when a setup fails deterministic N3 strategy approval."""

    def __init__(self, decision: StrategyApprovalDecision) -> None:
        self.decision = decision
        super().__init__(tuple(reason.message for reason in decision.reasons))


def build_futures_plan(
    setup: RiskApprovedSetup,
    account: FuturesAccountInput,
    *,
    product_config: FuturesProductConfig | None = None,
    strategy_approval_config: StrategyApprovalConfig | None = None,
    account_policy: AccountPolicy | None = None,
    account_policy_state: AccountPolicyState | None = None,
    historical_evidence_available: bool = False,
) -> dict[str, object]:
    """Build a futures plan after quality, mode, and account-policy checks."""

    config = product_config or load_futures_product_config("config/futures.yaml")
    approval_config = strategy_approval_config or load_strategy_approval_config(
        DEFAULT_STRATEGY_APPROVAL_CONFIG_PATH
    )
    defaults = config.defaults_for(account.risk_mode)
    mode_reasons = list(_risk_mode_rejection_reasons(account, defaults, account_policy_state))

    policy_decision = _evaluate_policy(account, account_policy, account_policy_state)
    if policy_decision is not None and not policy_decision.approved:
        mode_reasons.extend(
            f"account policy lockout: {reason.value}" for reason in policy_decision.lockout_reasons
        )
    if mode_reasons:
        raise FuturesPlanSafetyError(tuple(mode_reasons))

    plan = _build_futures_plan(setup, account, product_config=config)
    entry = EntryPlan.model_validate(plan["entry"])
    strategy_decision = evaluate_strategy_approval(
        strategy=setup.strategy,
        risk_mode=account.risk_mode,
        score=setup.confidence_score,
        entry_state=entry.state,
        config=approval_config,
        account_policy_decision=policy_decision,
        historical_evidence_available=historical_evidence_available,
    )
    if not strategy_decision.approved:
        raise StrategyApprovalError(strategy_decision)

    direction = FuturesDirection(setup.direction.value.upper())
    management_plan = build_trade_management_plan(
        direction=direction,
        entry=entry,
        position=PositionPlan.model_validate(plan["position"]),
        targets=TargetPlan.model_validate(plan["targets"]),
        account=account,
        generated_at=setup.decision_time,
    )
    plan["management_plan"] = management_plan.model_dump(mode="json")
    plan["risk_mode"] = account.risk_mode.value
    plan["risk_mode_config"] = defaults.model_dump(mode="json")
    plan["strategy_approval"] = strategy_decision.to_payload()
    plan["eligibility"] = strategy_decision.eligibility.value
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
    strategy_approval_config: StrategyApprovalConfig | None = None,
    account_policy: AccountPolicy | None = None,
    account_policy_state: AccountPolicyState | None = None,
    historical_evidence_available: bool = False,
) -> dict[str, object]:
    """Return an approved or rejected policy-aware futures-plan payload."""

    try:
        return build_futures_plan(
            setup,
            account,
            product_config=product_config,
            strategy_approval_config=strategy_approval_config,
            account_policy=account_policy,
            account_policy_state=account_policy_state,
            historical_evidence_available=historical_evidence_available,
        )
    except StrategyApprovalError as exc:
        return {
            "status": "REJECTED",
            "risk_mode": account.risk_mode.value,
            "eligibility": exc.decision.eligibility.value,
            "strategy_approval": exc.decision.to_payload(),
            "reasons": [reason.message for reason in exc.decision.reasons],
        }
    except FuturesPlanSafetyError as exc:
        return {
            "status": "REJECTED",
            "risk_mode": account.risk_mode.value,
            "eligibility": "REJECTED",
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
    defaults: RiskModeDefaults,
    state: AccountPolicyState | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if account.maximum_account_loss_percentage > defaults.account_loss_percentage:
        reasons.append(
            f"account loss {account.maximum_account_loss_percentage:.2f}% exceeds "
            f"{account.risk_mode.value} mode limit {defaults.account_loss_percentage:.2f}%"
        )
    if state is not None:
        daily_drawdown = max(
            0.0,
            (state.start_of_day_equity - state.current_equity) / state.start_of_day_equity * 100.0,
        )
        if daily_drawdown >= defaults.maximum_daily_loss_percentage:
            reasons.append(
                f"daily drawdown {daily_drawdown:.2f}% reached "
                f"{account.risk_mode.value} mode limit "
                f"{defaults.maximum_daily_loss_percentage:.2f}%"
            )
        if state.consecutive_losses >= defaults.maximum_consecutive_losses:
            reasons.append(
                f"consecutive losses {state.consecutive_losses} reached "
                f"{account.risk_mode.value} mode limit "
                f"{defaults.maximum_consecutive_losses}"
            )
        projected_open_risk = state.total_open_risk_pct + account.maximum_account_loss_percentage
        if projected_open_risk > defaults.maximum_open_risk_percentage:
            reasons.append(
                f"projected open risk {projected_open_risk:.2f}% exceeds "
                f"{account.risk_mode.value} mode limit "
                f"{defaults.maximum_open_risk_percentage:.2f}%"
            )
    return tuple(reasons)
