"""Resolve policy-aware futures account context for CLI and runtime callers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from apex.application.account_state import AccountStateSnapshot, AccountStateStore
from apex.application.futures_account import build_futures_account_input
from apex.config import load_account_policies_config
from apex.domain import AccountPolicy, AccountPolicyState, FuturesAccountInput

DEFAULT_ACCOUNT_POLICIES_PATH = Path("config/account_policies.yaml")
DEFAULT_CLI_WALLET_BALANCE = 100.0


@dataclass(frozen=True, slots=True)
class ResolvedAccountContext:
    """Validated futures account, optional policy, and persistent policy state."""

    account: FuturesAccountInput
    policy: AccountPolicy | None
    policy_state: AccountPolicyState | None
    snapshot: AccountStateSnapshot | None


def resolve_account_context(
    *,
    wallet_balance: float | None = None,
    risk_mode: str | None = None,
    account_policy_name: str | None = None,
    account_state_file: str | Path | None = None,
    account_policies_file: str | Path = DEFAULT_ACCOUNT_POLICIES_PATH,
    session: str | None = None,
    is_weekend: bool = False,
) -> ResolvedAccountContext:
    """Resolve compact CLI inputs without duplicating persistent state fields."""

    snapshot = _load_snapshot(account_state_file)
    if account_policy_name is not None and snapshot is None:
        raise ValueError("account-policy selection requires an account-state file")
    if (
        snapshot is not None
        and account_policy_name is not None
        and account_policy_name != snapshot.policy_name
    ):
        raise ValueError(
            "account-policy selection must match the policy_name stored in account state"
        )

    resolved_wallet_balance = (
        wallet_balance
        if wallet_balance is not None
        else snapshot.current_equity
        if snapshot is not None
        else DEFAULT_CLI_WALLET_BALANCE
    )
    account = build_futures_account_input(
        wallet_balance=resolved_wallet_balance,
        risk_mode=risk_mode,
    )
    if snapshot is None:
        return ResolvedAccountContext(
            account=account,
            policy=None,
            policy_state=None,
            snapshot=None,
        )

    policy_name = account_policy_name or snapshot.policy_name
    policy = load_account_policies_config(account_policies_file).policy_for(policy_name)
    policy_state = snapshot.for_policy_evaluation(
        proposed_risk_pct=account.maximum_account_loss_percentage,
        proposed_has_stop_loss=True,
        is_weekend=is_weekend,
        session=session,
    )
    return ResolvedAccountContext(
        account=account,
        policy=policy,
        policy_state=policy_state,
        snapshot=snapshot,
    )


def _load_snapshot(path: str | Path | None) -> AccountStateSnapshot | None:
    if path is None:
        return None
    snapshot = AccountStateStore(path).load()
    if snapshot is None:
        raise ValueError(f"account-state file does not exist: {path}")
    return snapshot
