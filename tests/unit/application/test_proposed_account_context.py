from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from apex.application.account_context import resolve_account_context
from apex.application.account_state import AccountStateSnapshot, AccountStateStore


def _write_state(path: Path) -> None:
    AccountStateStore(path).save(
        AccountStateSnapshot(
            policy_name="PAPER",
            trading_day=date(2026, 7, 14),
            current_balance=1000.0,
            current_equity=1000.0,
            start_of_day_equity=1000.0,
            total_open_risk_pct=0.5,
            directional_exposure_pct=0.25,
            correlated_exposure_pct=0.1,
        )
    )


def test_resolve_account_context_preserves_proposed_exposure(tmp_path: Path) -> None:
    state_path = tmp_path / "account-state.json"
    _write_state(state_path)

    context = resolve_account_context(
        account_state_file=state_path,
        proposed_directional_exposure_pct=0.25,
        proposed_correlated_exposure_pct=0.1,
    )

    assert context.policy_state is not None
    assert context.policy_state.proposed_directional_exposure_pct == pytest.approx(0.25)
    assert context.policy_state.proposed_correlated_exposure_pct == pytest.approx(0.1)


def test_resolve_account_context_rejects_exposure_without_state() -> None:
    with pytest.raises(ValueError, match="require an account-state file"):
        resolve_account_context(proposed_directional_exposure_pct=0.25)
