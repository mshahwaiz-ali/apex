"""Tests for deterministic persistent account state."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from apex.application import AccountStateSnapshot, AccountStateStore


def _snapshot() -> AccountStateSnapshot:
    return AccountStateSnapshot(
        policy_name="FUNDED_GENERIC",
        trading_day=date(2026, 7, 14),
        current_balance=50000.0,
        current_equity=50000.0,
        start_of_day_equity=50000.0,
    )


def test_entry_and_close_update_counters_and_exposure() -> None:
    opened = _snapshot().register_entry(
        risk_pct=0.25,
        directional_risk_pct=0.25,
        correlated_risk_pct=0.10,
    )

    assert opened.trades_today == 1
    assert opened.total_open_risk_pct == 0.25
    assert opened.directional_exposure_pct == 0.25

    closed = opened.register_close(
        realized_pnl=-100.0,
        released_risk_pct=0.25,
        released_directional_risk_pct=0.25,
        released_correlated_risk_pct=0.10,
        current_equity=49900.0,
    )

    assert closed.current_balance == 49900.0
    assert closed.consecutive_losses == 1
    assert closed.total_open_risk_pct == 0.0


def test_profitable_close_resets_loss_streak() -> None:
    snapshot = _snapshot().model_copy(update={"consecutive_losses": 2})

    closed = snapshot.register_close(
        realized_pnl=50.0,
        released_risk_pct=0.0,
        released_directional_risk_pct=0.0,
        released_correlated_risk_pct=0.0,
        current_equity=50050.0,
    )

    assert closed.consecutive_losses == 0


def test_day_roll_resets_daily_trade_count() -> None:
    snapshot = _snapshot().register_entry(
        risk_pct=0.25,
        directional_risk_pct=0.25,
        correlated_risk_pct=0.10,
    )

    rolled = snapshot.roll_to_day(date(2026, 7, 15))

    assert rolled.trades_today == 0
    assert rolled.start_of_day_equity == snapshot.current_equity
    assert rolled.total_open_risk_pct == snapshot.total_open_risk_pct


def test_day_roll_cannot_move_backward() -> None:
    with pytest.raises(ValueError, match="cannot roll backward"):
        _snapshot().roll_to_day(date(2026, 7, 13))


def test_transition_revalidates_exposure_geometry() -> None:
    with pytest.raises(ValidationError, match="directional exposure cannot exceed total open risk"):
        _snapshot().register_entry(
            risk_pct=0.10,
            directional_risk_pct=0.20,
            correlated_risk_pct=0.0,
        )


def test_store_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "account-state.json"
    store = AccountStateStore(path)
    snapshot = _snapshot()

    assert store.load() is None
    store.save(snapshot)

    assert store.load() == snapshot
