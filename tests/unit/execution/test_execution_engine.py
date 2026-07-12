from datetime import UTC, datetime

from apex.execution import (
    ExecutionConfig,
    ExecutionState,
    KillSwitchState,
    load_duplicate_keys,
    submit_testnet_order,
)
from apex.execution.contracts import ExecutionIntent
from apex.strategies import TradeDirection

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _intent() -> ExecutionIntent:
    return ExecutionIntent(
        symbol="BTC/USDT",
        direction=TradeDirection.LONG,
        quantity=1.0,
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        notional_value=100.0,
        duplicate_key="abc123",
    )


def test_execution_is_disabled_by_default(tmp_path) -> None:
    result = submit_testnet_order(
        _intent(),
        config=ExecutionConfig(),
        audit_log=tmp_path / "audit.jsonl",
        kill_switch=KillSwitchState.DISABLED,
        confirmed=True,
        now=NOW,
    )

    assert result.state is ExecutionState.REJECTED
    assert result.reasons == ("execution is disabled",)


def test_confirmed_testnet_order_writes_audit_and_duplicate_key(tmp_path) -> None:
    audit = tmp_path / "audit.jsonl"
    result = submit_testnet_order(
        _intent(),
        config=ExecutionConfig(enabled=True),
        audit_log=audit,
        kill_switch=KillSwitchState.DISABLED,
        confirmed=True,
        now=NOW,
    )

    assert result.state is ExecutionState.TESTNET_SUBMITTED
    assert audit.exists()
    assert load_duplicate_keys(audit) == {"abc123"}


def test_duplicate_and_kill_switch_reject_order(tmp_path) -> None:
    result = submit_testnet_order(
        _intent(),
        config=ExecutionConfig(enabled=True),
        audit_log=tmp_path / "audit.jsonl",
        kill_switch=KillSwitchState.ENABLED,
        confirmed=True,
        existing_duplicate_keys={"abc123"},
        now=NOW,
    )

    assert result.state is ExecutionState.REJECTED
    assert "kill switch is enabled" in result.reasons
    assert "duplicate order key already submitted" in result.reasons
