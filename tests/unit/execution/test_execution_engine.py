import json
from datetime import UTC, datetime

import pytest

from apex.execution import (
    EXECUTION_AUDIT_SCHEMA_VERSION,
    EXECUTION_RECONCILIATION_SCHEMA_VERSION,
    DeterministicFakeTestnetAdapter,
    ExecutionAdapterSnapshot,
    ExecutionConfig,
    ExecutionEnvironment,
    ExecutionState,
    KillSwitchState,
    build_execution_readiness_report,
    client_order_id,
    idempotency_key,
    load_duplicate_keys,
    preview_execution,
    readiness_report_payload,
    reconcile_execution_audit,
    reconciliation_report_payload,
    simulate_testnet_order,
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


def _ladder_intent() -> ExecutionIntent:
    return ExecutionIntent(
        symbol="BTC/USDT",
        direction=TradeDirection.LONG,
        quantity=1.0,
        entry_price=100.0,
        stop_price=98.0,
        target_price=102.0,
        notional_value=100.0,
        duplicate_key="ladder123",
        target_prices=(102.0, 104.0),
        partial_close_percentages=(50.0, 50.0),
    )


def test_execution_intent_preserves_target_ladder() -> None:
    intent = _ladder_intent()

    assert intent.target_price == 102.0
    assert intent.target_prices == (102.0, 104.0)
    assert intent.partial_close_percentages == (50.0, 50.0)


def test_execution_intent_rejects_invalid_target_ladder() -> None:
    with pytest.raises(ValueError, match="sum to 100"):
        ExecutionIntent(
            symbol="BTC/USDT",
            direction=TradeDirection.LONG,
            quantity=1.0,
            entry_price=100.0,
            stop_price=98.0,
            target_price=102.0,
            notional_value=100.0,
            duplicate_key="bad",
            target_prices=(102.0, 104.0),
            partial_close_percentages=(40.0, 40.0),
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


def test_execution_config_rejects_non_testnet_environment() -> None:
    with pytest.raises(ValueError, match="local testnet simulation"):
        ExecutionConfig(enabled=True, environment="live")

    with pytest.raises(ValueError, match="local testnet simulation"):
        ExecutionConfig(enabled=True, testnet=False)


def test_preview_uses_deterministic_local_testnet_identities() -> None:
    result = preview_execution(_intent(), now=NOW)

    assert result.order is not None
    assert result.order.environment is ExecutionEnvironment.LOCAL_TESTNET_SIMULATION
    assert result.order.client_order_id == client_order_id(_intent())
    assert result.order.idempotency_key == idempotency_key(_intent())


def test_idempotency_key_includes_target_ladder() -> None:
    first = _ladder_intent()
    second = ExecutionIntent(
        symbol="BTC/USDT",
        direction=TradeDirection.LONG,
        quantity=1.0,
        entry_price=100.0,
        stop_price=98.0,
        target_price=102.0,
        notional_value=100.0,
        duplicate_key="ladder123",
        target_prices=(102.0, 105.0),
        partial_close_percentages=(50.0, 50.0),
    )

    assert idempotency_key(first) != idempotency_key(second)


def test_confirmed_local_testnet_simulation_writes_audit_and_duplicate_key(tmp_path) -> None:
    audit = tmp_path / "audit.jsonl"
    result = simulate_testnet_order(
        _intent(),
        config=ExecutionConfig(enabled=True),
        audit_log=audit,
        kill_switch=KillSwitchState.DISABLED,
        confirmed=True,
        now=NOW,
    )

    assert result.state is ExecutionState.LOCAL_TESTNET_SIMULATED
    assert result.order is not None
    assert result.order.order_id == "local-sim-abc123"
    assert result.order.environment is ExecutionEnvironment.LOCAL_TESTNET_SIMULATION
    assert result.order.client_order_id == "apex-local_testnet_simulation-BTCUSDT-abc123"
    assert result.order.idempotency_key == idempotency_key(_intent())
    assert audit.exists()
    assert "local_testnet_simulated" in audit.read_text(encoding="utf-8")
    assert load_duplicate_keys(audit) == {"abc123"}
    audit_event = json.loads(audit.read_text(encoding="utf-8"))
    assert audit_event["schema_version"] == EXECUTION_AUDIT_SCHEMA_VERSION
    assert audit_event["environment"] == ExecutionEnvironment.LOCAL_TESTNET_SIMULATION.value
    assert audit_event["testnet_only"] is True
    assert audit_event["live_fallback"] is False
    assert audit_event["adapter_name"] == "local-simulation"
    assert audit_event["order"]["client_order_id"] == result.order.client_order_id
    assert audit_event["order"]["idempotency_key"] == result.order.idempotency_key


def test_simulated_audit_records_execution_target_ladder(tmp_path) -> None:
    audit = tmp_path / "audit.jsonl"
    result = simulate_testnet_order(
        _ladder_intent(),
        config=ExecutionConfig(enabled=True),
        audit_log=audit,
        kill_switch=KillSwitchState.DISABLED,
        confirmed=True,
        now=NOW,
    )

    assert result.state is ExecutionState.LOCAL_TESTNET_SIMULATED
    audit_event = json.loads(audit.read_text(encoding="utf-8"))
    assert audit_event["order"]["intent"]["target_prices"] == [102.0, 104.0]
    assert audit_event["order"]["intent"]["partial_close_percentages"] == [50.0, 50.0]


def test_legacy_submit_testnet_order_uses_local_simulation_state(tmp_path) -> None:
    result = submit_testnet_order(
        _intent(),
        config=ExecutionConfig(enabled=True),
        audit_log=tmp_path / "audit.jsonl",
        kill_switch=KillSwitchState.DISABLED,
        confirmed=True,
        now=NOW,
    )

    assert result.state is ExecutionState.LOCAL_TESTNET_SIMULATED


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
    assert "duplicate order key already recorded" in result.reasons


def test_deterministic_fake_testnet_adapter_uses_same_safety_gates(tmp_path) -> None:
    adapter = DeterministicFakeTestnetAdapter()
    audit = tmp_path / "audit.jsonl"

    result = adapter.submit_order(
        _intent(),
        config=ExecutionConfig(enabled=True),
        audit_log=audit,
        kill_switch=KillSwitchState.DISABLED,
        confirmed=True,
        now=NOW,
    )

    assert adapter.testnet_only is True
    assert adapter.live_fallback is False
    assert result.state is ExecutionState.LOCAL_TESTNET_SIMULATED
    assert result.adapter_name == "deterministic-fake-testnet"
    audit_event = json.loads(audit.read_text(encoding="utf-8"))
    assert audit_event["adapter_name"] == "deterministic-fake-testnet"
    assert audit_event["live_fallback"] is False


def test_fake_adapter_rejects_unconfirmed_order(tmp_path) -> None:
    result = DeterministicFakeTestnetAdapter().submit_order(
        _intent(),
        config=ExecutionConfig(enabled=False),
        audit_log=tmp_path / "audit.jsonl",
        kill_switch=KillSwitchState.DISABLED,
        confirmed=False,
        now=NOW,
    )

    assert result.state is ExecutionState.REJECTED
    assert "execution is disabled" in result.reasons
    assert "explicit confirmation is required" in result.reasons


def test_execution_reconciliation_matches_adapter_snapshot(tmp_path) -> None:
    audit = tmp_path / "audit.jsonl"
    result = simulate_testnet_order(
        _intent(),
        config=ExecutionConfig(enabled=True),
        audit_log=audit,
        kill_switch=KillSwitchState.DISABLED,
        confirmed=True,
        now=NOW,
    )
    assert result.order is not None

    report = reconcile_execution_audit(
        audit,
        adapter_snapshots=(
            ExecutionAdapterSnapshot(
                client_order_id=result.order.client_order_id or "",
                order_id=result.order.order_id,
                state=ExecutionState.LOCAL_TESTNET_SIMULATED,
                filled_quantity=1.0,
                average_fill_price=100.0,
            ),
        ),
        generated_at=NOW,
    )
    payload = reconciliation_report_payload(report)

    assert payload["schema_version"] == EXECUTION_RECONCILIATION_SCHEMA_VERSION
    assert report.matched_count == 1
    assert report.missing_count == 0
    assert report.records[0].reasons == ()


def test_execution_reconciliation_reports_missing_and_mismatched_snapshots(tmp_path) -> None:
    audit = tmp_path / "audit.jsonl"
    first = simulate_testnet_order(
        _intent(),
        config=ExecutionConfig(enabled=True),
        audit_log=audit,
        kill_switch=KillSwitchState.DISABLED,
        confirmed=True,
        now=NOW,
    )
    second = simulate_testnet_order(
        _ladder_intent(),
        config=ExecutionConfig(enabled=True),
        audit_log=audit,
        kill_switch=KillSwitchState.DISABLED,
        confirmed=True,
        now=NOW,
    )
    assert first.order is not None
    assert second.order is not None

    report = reconcile_execution_audit(
        audit,
        adapter_snapshots=(
            ExecutionAdapterSnapshot(
                client_order_id=first.order.client_order_id or "",
                order_id="adapter-1",
                state=ExecutionState.PREVIEW,
            ),
        ),
        generated_at=NOW,
    )

    assert report.matched_count == 0
    assert report.mismatched_count == 1
    assert report.missing_count == 1
    assert "state differs" in " ".join(report.records[0].reasons)


def test_execution_reconciliation_keeps_rejected_local_events(tmp_path) -> None:
    audit = tmp_path / "audit.jsonl"
    simulate_testnet_order(
        _intent(),
        config=ExecutionConfig(enabled=False),
        audit_log=audit,
        kill_switch=KillSwitchState.DISABLED,
        confirmed=False,
        now=NOW,
    )

    report = reconcile_execution_audit(audit, generated_at=NOW)

    assert report.rejected_local_count == 1
    assert report.records[0].client_order_id is None
    assert "execution is disabled" in report.records[0].reasons


def test_execution_readiness_reports_local_boundary_and_exchange_blockers(tmp_path) -> None:
    audit = tmp_path / "audit.jsonl"
    result = simulate_testnet_order(
        _intent(),
        config=ExecutionConfig(enabled=True),
        audit_log=audit,
        kill_switch=KillSwitchState.DISABLED,
        confirmed=True,
        now=NOW,
    )
    assert result.order is not None
    reconciliation = reconcile_execution_audit(
        audit,
        adapter_snapshots=(
            ExecutionAdapterSnapshot(
                client_order_id=result.order.client_order_id or "",
                order_id=result.order.order_id,
                state=ExecutionState.LOCAL_TESTNET_SIMULATED,
            ),
        ),
        generated_at=NOW,
    )

    readiness = build_execution_readiness_report(
        audit_log=audit,
        kill_switch=KillSwitchState.DISABLED,
        reconciliation=reconciliation,
        generated_at=NOW,
    )
    payload = readiness_report_payload(readiness)

    assert payload["schema_version"] == 1
    assert readiness.local_simulation_ready is True
    assert readiness.exchange_ready is False
    assert readiness.blockers
    assert not readiness.warnings


def test_execution_readiness_fails_on_kill_switch_or_bad_reconciliation(tmp_path) -> None:
    audit = tmp_path / "audit.jsonl"
    simulate_testnet_order(
        _intent(),
        config=ExecutionConfig(enabled=True),
        audit_log=audit,
        kill_switch=KillSwitchState.DISABLED,
        confirmed=True,
        now=NOW,
    )
    reconciliation = reconcile_execution_audit(audit, generated_at=NOW)

    readiness = build_execution_readiness_report(
        audit_log=audit,
        kill_switch=KillSwitchState.ENABLED,
        reconciliation=reconciliation,
        generated_at=NOW,
    )

    assert readiness.local_simulation_ready is False
    assert any(gate.status.value == "fail" for gate in readiness.gates)
