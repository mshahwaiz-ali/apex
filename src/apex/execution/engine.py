"""Local testnet simulation safety engine."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apex.execution.contracts import (
    EXECUTION_AUDIT_SCHEMA_VERSION,
    EXECUTION_READINESS_SCHEMA_VERSION,
    EXECUTION_RECONCILIATION_SCHEMA_VERSION,
    ExecutionAdapterSnapshot,
    ExecutionConfig,
    ExecutionEnvironment,
    ExecutionIntent,
    ExecutionOrder,
    ExecutionReadinessGate,
    ExecutionReadinessGateStatus,
    ExecutionReadinessReport,
    ExecutionReconciliationRecord,
    ExecutionReconciliationReport,
    ExecutionReconciliationStatus,
    ExecutionResult,
    ExecutionState,
    KillSwitchState,
)
from apex.risk.contracts import RiskApprovedSetup


def intent_from_setup(setup: RiskApprovedSetup) -> ExecutionIntent:
    """Create an execution intent from an approved setup without submitting it."""

    duplicate_key = _digest(setup.symbol, setup.candidate_id, setup.decision_time.isoformat())
    targets = tuple(target.price for target in setup.take_profits)
    return ExecutionIntent(
        symbol=setup.symbol,
        direction=setup.direction,
        quantity=setup.position_size.quantity,
        entry_price=setup.entry.preferred,
        stop_price=setup.stop_loss.price,
        target_price=targets[0],
        notional_value=setup.position_size.notional_value,
        duplicate_key=duplicate_key,
        target_prices=targets,
        partial_close_percentages=tuple(target.partial_close_pct for target in setup.take_profits),
    )


def preview_execution(intent: ExecutionIntent, *, now: datetime | None = None) -> ExecutionResult:
    timestamp = now or datetime.now(UTC)
    environment = ExecutionEnvironment.LOCAL_TESTNET_SIMULATION
    order = ExecutionOrder(
        order_id=f"preview-{intent.duplicate_key}",
        intent=intent,
        state=ExecutionState.PREVIEW,
        created_at=timestamp,
        environment=environment,
        client_order_id=client_order_id(intent, environment=environment),
        idempotency_key=idempotency_key(intent, environment=environment),
    )
    return ExecutionResult(state=ExecutionState.PREVIEW, order=order, reasons=())


def simulate_testnet_order(
    intent: ExecutionIntent,
    *,
    config: ExecutionConfig,
    audit_log: Path,
    kill_switch: KillSwitchState,
    confirmed: bool,
    existing_duplicate_keys: set[str] | None = None,
    daily_realized_loss: float = 0.0,
    now: datetime | None = None,
    adapter_name: str = "local-simulation",
) -> ExecutionResult:
    """Record a local simulated testnet order only when all safety gates pass."""

    reasons = _rejection_reasons(
        intent,
        config=config,
        kill_switch=kill_switch,
        confirmed=confirmed,
        existing_duplicate_keys=existing_duplicate_keys or set(),
        daily_realized_loss=daily_realized_loss,
    )
    timestamp = now or datetime.now(UTC)
    if reasons:
        result = ExecutionResult(
            state=ExecutionState.REJECTED,
            order=None,
            reasons=tuple(reasons),
            audit_path=str(audit_log),
            adapter_name=adapter_name,
        )
        append_audit_event(audit_log, result, timestamp=timestamp)
        return result
    environment = _execution_environment(config)
    order = ExecutionOrder(
        order_id=f"local-sim-{intent.duplicate_key}",
        intent=intent,
        state=ExecutionState.LOCAL_TESTNET_SIMULATED,
        created_at=timestamp,
        environment=environment,
        client_order_id=client_order_id(intent, environment=environment),
        idempotency_key=idempotency_key(intent, environment=environment),
    )
    result = ExecutionResult(
        state=ExecutionState.LOCAL_TESTNET_SIMULATED,
        order=order,
        reasons=(),
        audit_path=str(audit_log),
        adapter_name=adapter_name,
    )
    append_audit_event(audit_log, result, timestamp=timestamp)
    return result


def submit_testnet_order(
    intent: ExecutionIntent,
    *,
    config: ExecutionConfig,
    audit_log: Path,
    kill_switch: KillSwitchState,
    confirmed: bool,
    existing_duplicate_keys: set[str] | None = None,
    daily_realized_loss: float = 0.0,
    now: datetime | None = None,
    adapter_name: str = "local-simulation",
) -> ExecutionResult:
    """Backward-compatible alias for local testnet simulation."""

    return simulate_testnet_order(
        intent,
        config=config,
        audit_log=audit_log,
        kill_switch=kill_switch,
        confirmed=confirmed,
        existing_duplicate_keys=existing_duplicate_keys,
        daily_realized_loss=daily_realized_loss,
        now=now,
        adapter_name=adapter_name,
    )


def append_audit_event(path: Path, result: ExecutionResult, *, timestamp: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    environment = (
        result.order.environment.value
        if result.order is not None
        else ExecutionEnvironment.LOCAL_TESTNET_SIMULATION.value
    )
    event = {
        "schema_version": EXECUTION_AUDIT_SCHEMA_VERSION,
        "timestamp": timestamp.isoformat(),
        "environment": environment,
        "testnet_only": True,
        "live_fallback": False,
        "adapter_name": result.adapter_name,
        "state": result.state.value,
        "reasons": list(result.reasons),
        "order": _jsonable(asdict(result.order)) if result.order is not None else None,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def load_duplicate_keys(path: Path) -> set[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return set()
    keys: set[str] = set()
    for line in lines:
        payload = json.loads(line)
        order = payload.get("order")
        if isinstance(order, dict):
            intent = order.get("intent")
            if isinstance(intent, dict) and isinstance(intent.get("duplicate_key"), str):
                keys.add(intent["duplicate_key"])
    return keys


def reconcile_execution_audit(
    audit_log: Path,
    *,
    adapter_snapshots: tuple[ExecutionAdapterSnapshot, ...] = (),
    adapter_name: str = "local-simulation",
    generated_at: datetime | None = None,
) -> ExecutionReconciliationReport:
    """Compare local execution audit events with deterministic adapter snapshots."""

    snapshot_by_client_id = {snapshot.client_order_id: snapshot for snapshot in adapter_snapshots}
    records: list[ExecutionReconciliationRecord] = []
    for event in load_execution_audit_events(audit_log):
        order = event.get("order")
        state = ExecutionState(str(event.get("state", ExecutionState.REJECTED.value)))
        if not isinstance(order, dict):
            records.append(
                ExecutionReconciliationRecord(
                    status=ExecutionReconciliationStatus.REJECTED_LOCAL,
                    audit_state=state,
                    client_order_id=None,
                    local_order_id=None,
                    adapter_order_id=None,
                    reasons=tuple(str(reason) for reason in event.get("reasons", []))
                    or ("local execution was rejected",),
                )
            )
            continue
        client_order = order.get("client_order_id")
        local_order = order.get("order_id")
        client_order_id_value = str(client_order) if isinstance(client_order, str) else None
        local_order_id_value = str(local_order) if isinstance(local_order, str) else None
        snapshot = (
            snapshot_by_client_id.get(client_order_id_value)
            if client_order_id_value is not None
            else None
        )
        if snapshot is None:
            records.append(
                ExecutionReconciliationRecord(
                    status=ExecutionReconciliationStatus.MISSING_ADAPTER_ORDER,
                    audit_state=state,
                    client_order_id=client_order_id_value,
                    local_order_id=local_order_id_value,
                    adapter_order_id=None,
                    reasons=("adapter snapshot is missing for audited client order",),
                )
            )
            continue
        reasons = _snapshot_mismatch_reasons(order, snapshot, state)
        records.append(
            ExecutionReconciliationRecord(
                status=(
                    ExecutionReconciliationStatus.MISMATCHED
                    if reasons
                    else ExecutionReconciliationStatus.MATCHED
                ),
                audit_state=state,
                client_order_id=client_order_id_value,
                local_order_id=local_order_id_value,
                adapter_order_id=snapshot.order_id,
                reasons=tuple(reasons),
            )
        )

    return _build_reconciliation_report(
        audit_log,
        records=tuple(records),
        adapter_name=adapter_name,
        generated_at=generated_at or datetime.now(UTC),
    )


def load_execution_audit_events(path: Path) -> tuple[dict[str, Any], ...]:
    """Load local execution audit JSONL events, skipping blank lines."""

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ()
    events: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError("execution audit events must be JSON objects")
        events.append(payload)
    return tuple(events)


def reconciliation_report_payload(report: ExecutionReconciliationReport) -> dict[str, Any]:
    """Serialize an execution reconciliation report for JSON output."""

    return {
        "schema_version": EXECUTION_RECONCILIATION_SCHEMA_VERSION,
        "generated_at": report.generated_at.isoformat(),
        "audit_path": report.audit_path,
        "adapter_name": report.adapter_name,
        "total_audit_events": report.total_audit_events,
        "matched_count": report.matched_count,
        "missing_count": report.missing_count,
        "mismatched_count": report.mismatched_count,
        "rejected_local_count": report.rejected_local_count,
        "records": [
            {
                "status": record.status.value,
                "audit_state": record.audit_state.value,
                "client_order_id": record.client_order_id,
                "local_order_id": record.local_order_id,
                "adapter_order_id": record.adapter_order_id,
                "reasons": list(record.reasons),
            }
            for record in report.records
        ],
    }


def build_execution_readiness_report(
    *,
    audit_log: Path,
    kill_switch: KillSwitchState,
    reconciliation: ExecutionReconciliationReport | None = None,
    generated_at: datetime | None = None,
) -> ExecutionReadinessReport:
    """Build a deterministic execution-readiness report without exchange access."""

    audit_events = load_execution_audit_events(audit_log)
    gates = [
        ExecutionReadinessGate(
            name="environment",
            status=ExecutionReadinessGateStatus.PASS,
            detail="only local testnet simulation is supported",
        ),
        ExecutionReadinessGate(
            name="live_fallback",
            status=ExecutionReadinessGateStatus.PASS,
            detail="live fallback is disabled",
        ),
        ExecutionReadinessGate(
            name="kill_switch",
            status=(
                ExecutionReadinessGateStatus.PASS
                if kill_switch is KillSwitchState.DISABLED
                else ExecutionReadinessGateStatus.FAIL
            ),
            detail=f"kill switch is {kill_switch.value}",
        ),
        ExecutionReadinessGate(
            name="audit_log",
            status=(
                ExecutionReadinessGateStatus.PASS
                if audit_events
                else ExecutionReadinessGateStatus.WARN
            ),
            detail=f"{len(audit_events)} audit events found",
        ),
        _readiness_reconciliation_gate(reconciliation),
    ]
    warnings = tuple(
        gate.detail for gate in gates if gate.status is ExecutionReadinessGateStatus.WARN
    )
    blockers = (
        "exchange-specific testnet adapter is not configured",
        "exchange credentials were not used",
        "exchange-side order reconciliation has not been validated",
        "production exchange execution remains outside current scope",
    )
    return ExecutionReadinessReport(
        generated_at=generated_at or datetime.now(UTC),
        mode="local_testnet_simulation_only",
        local_simulation_ready=not any(
            gate.status is ExecutionReadinessGateStatus.FAIL for gate in gates
        ),
        exchange_ready=False,
        gates=tuple(gates),
        blockers=blockers,
        warnings=warnings,
    )


def readiness_report_payload(report: ExecutionReadinessReport) -> dict[str, Any]:
    """Serialize an execution readiness report for JSON output."""

    return {
        "schema_version": EXECUTION_READINESS_SCHEMA_VERSION,
        "generated_at": report.generated_at.isoformat(),
        "mode": report.mode,
        "local_simulation_ready": report.local_simulation_ready,
        "exchange_ready": report.exchange_ready,
        "gates": [
            {
                "name": gate.name,
                "status": gate.status.value,
                "detail": gate.detail,
            }
            for gate in report.gates
        ],
        "blockers": list(report.blockers),
        "warnings": list(report.warnings),
    }


class DeterministicFakeTestnetAdapter:
    """Provider-independent fake testnet adapter with no exchange connectivity."""

    name = "deterministic-fake-testnet"
    testnet_only = True
    live_fallback = False

    def submit_order(
        self,
        intent: ExecutionIntent,
        *,
        config: ExecutionConfig,
        audit_log: Path,
        kill_switch: KillSwitchState,
        confirmed: bool,
        existing_duplicate_keys: set[str] | None = None,
        daily_realized_loss: float = 0.0,
        now: datetime | None = None,
    ) -> ExecutionResult:
        return simulate_testnet_order(
            intent,
            config=config,
            audit_log=audit_log,
            kill_switch=kill_switch,
            confirmed=confirmed,
            existing_duplicate_keys=existing_duplicate_keys,
            daily_realized_loss=daily_realized_loss,
            now=now,
            adapter_name=self.name,
        )


def client_order_id(
    intent: ExecutionIntent,
    *,
    environment: ExecutionEnvironment = ExecutionEnvironment.LOCAL_TESTNET_SIMULATION,
) -> str:
    """Return a deterministic exchange-safe client order identity."""

    normalized_symbol = intent.symbol.replace("/", "").replace("-", "").upper()
    return f"apex-{environment.value}-{normalized_symbol}-{intent.duplicate_key}"


def idempotency_key(
    intent: ExecutionIntent,
    *,
    environment: ExecutionEnvironment = ExecutionEnvironment.LOCAL_TESTNET_SIMULATION,
) -> str:
    """Return a deterministic idempotency key scoped to execution environment."""

    payload = (
        environment.value,
        intent.symbol.upper(),
        intent.direction.value,
        f"{intent.quantity:.12g}",
        f"{intent.entry_price:.12g}",
        f"{intent.stop_price:.12g}",
        f"{intent.target_price:.12g}",
        ",".join(f"{target:.12g}" for target in intent.target_prices),
        ",".join(f"{partial:.12g}" for partial in intent.partial_close_percentages),
        f"{intent.notional_value:.12g}",
        intent.duplicate_key,
    )
    return f"exec-{_digest(*payload)}"


def _rejection_reasons(
    intent: ExecutionIntent,
    *,
    config: ExecutionConfig,
    kill_switch: KillSwitchState,
    confirmed: bool,
    existing_duplicate_keys: set[str],
    daily_realized_loss: float,
) -> list[str]:
    reasons: list[str] = []
    if not config.enabled:
        reasons.append("execution is disabled")
    if not config.testnet:
        reasons.append("only local testnet simulation is supported")
    if not confirmed:
        reasons.append("explicit confirmation is required")
    if kill_switch is KillSwitchState.ENABLED:
        reasons.append("kill switch is enabled")
    if intent.notional_value > config.max_order_notional:
        reasons.append("order notional exceeds configured maximum")
    if intent.duplicate_key in existing_duplicate_keys:
        reasons.append("duplicate order key already recorded")
    if daily_realized_loss >= config.daily_loss_limit:
        reasons.append("daily loss circuit breaker is active")
    return reasons


def _execution_environment(config: ExecutionConfig) -> ExecutionEnvironment:
    environment = config.environment
    if not isinstance(environment, ExecutionEnvironment):
        raise ValueError("execution config environment is invalid")
    return environment


def _snapshot_mismatch_reasons(
    order: dict[str, Any],
    snapshot: ExecutionAdapterSnapshot,
    audit_state: ExecutionState,
) -> list[str]:
    reasons: list[str] = []
    if snapshot.state is not audit_state:
        reasons.append("adapter state differs from audit state")
    intent = order.get("intent")
    if isinstance(intent, dict):
        quantity = intent.get("quantity")
        if isinstance(quantity, int | float) and snapshot.filled_quantity > float(quantity):
            reasons.append("adapter filled quantity exceeds intended quantity")
    return reasons


def _build_reconciliation_report(
    audit_log: Path,
    *,
    records: tuple[ExecutionReconciliationRecord, ...],
    adapter_name: str,
    generated_at: datetime,
) -> ExecutionReconciliationReport:
    return ExecutionReconciliationReport(
        generated_at=generated_at,
        audit_path=str(audit_log),
        adapter_name=adapter_name,
        total_audit_events=len(records),
        matched_count=sum(
            record.status is ExecutionReconciliationStatus.MATCHED for record in records
        ),
        missing_count=sum(
            record.status is ExecutionReconciliationStatus.MISSING_ADAPTER_ORDER
            for record in records
        ),
        mismatched_count=sum(
            record.status is ExecutionReconciliationStatus.MISMATCHED for record in records
        ),
        rejected_local_count=sum(
            record.status is ExecutionReconciliationStatus.REJECTED_LOCAL for record in records
        ),
        records=records,
    )


def _readiness_reconciliation_gate(
    reconciliation: ExecutionReconciliationReport | None,
) -> ExecutionReadinessGate:
    if reconciliation is None:
        return ExecutionReadinessGate(
            name="reconciliation",
            status=ExecutionReadinessGateStatus.WARN,
            detail="no reconciliation report supplied",
        )
    if reconciliation.missing_count or reconciliation.mismatched_count:
        return ExecutionReadinessGate(
            name="reconciliation",
            status=ExecutionReadinessGateStatus.FAIL,
            detail=(
                f"{reconciliation.missing_count} missing and "
                f"{reconciliation.mismatched_count} mismatched events"
            ),
        )
    return ExecutionReadinessGate(
        name="reconciliation",
        status=ExecutionReadinessGateStatus.PASS,
        detail=(
            f"{reconciliation.matched_count} matched and "
            f"{reconciliation.rejected_local_count} locally rejected events"
        ),
    )


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value
