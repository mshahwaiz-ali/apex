from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from apex.application.account_context import (
    DEFAULT_CLI_WALLET_BALANCE,
    resolve_account_context,
)
from apex.application.account_state import AccountStateSnapshot, AccountStateStore


def _write_state(path: Path, *, policy_name: str = "PAPER") -> None:
    AccountStateStore(path).save(
        AccountStateSnapshot(
            policy_name=policy_name,
            trading_day=date(2026, 7, 14),
            current_balance=990.0,
            current_equity=985.0,
            start_of_day_equity=1000.0,
            trades_today=1,
            consecutive_losses=1,
            total_open_risk_pct=0.5,
            directional_exposure_pct=0.25,
            correlated_exposure_pct=0.25,
        )
    )


def test_resolve_account_context_preserves_legacy_wallet_default() -> None:
    context = resolve_account_context()

    assert context.account.wallet_balance == DEFAULT_CLI_WALLET_BALANCE
    assert context.policy is None
    assert context.policy_state is None
    assert context.snapshot is None


def test_resolve_account_context_uses_snapshot_and_policy(tmp_path: Path) -> None:
    state_path = tmp_path / "account-state.json"
    _write_state(state_path)

    context = resolve_account_context(
        account_state_file=state_path,
        session="LONDON",
        is_weekend=True,
    )

    assert context.account.wallet_balance == 985.0
    assert context.policy is not None
    assert context.policy.type.value == "PAPER"
    assert context.policy_state is not None
    assert context.policy_state.trades_today == 1
    assert context.policy_state.session == "LONDON"
    assert context.policy_state.is_weekend is True


def test_resolve_account_context_rejects_policy_without_state() -> None:
    with pytest.raises(ValueError, match="requires an account-state file"):
        resolve_account_context(account_policy_name="FUNDED")


def test_resolve_account_context_rejects_policy_state_mismatch(tmp_path: Path) -> None:
    state_path = tmp_path / "account-state.json"
    _write_state(state_path, policy_name="PAPER")

    with pytest.raises(ValueError, match="must match"):
        resolve_account_context(
            account_policy_name="FUNDED",
            account_state_file=state_path,
        )
