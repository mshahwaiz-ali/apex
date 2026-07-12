"""Local testnet simulation safety engine."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apex.execution.contracts import (
    ExecutionConfig,
    ExecutionIntent,
    ExecutionOrder,
    ExecutionResult,
    ExecutionState,
    KillSwitchState,
)
from apex.risk.contracts import RiskApprovedSetup


def intent_from_setup(setup: RiskApprovedSetup) -> ExecutionIntent:
    """Create an execution intent from an approved setup without submitting it."""

    duplicate_key = _digest(setup.symbol, setup.candidate_id, setup.decision_time.isoformat())
    return ExecutionIntent(
        symbol=setup.symbol,
        direction=setup.direction,
        quantity=setup.position_size.quantity,
        entry_price=setup.entry.preferred,
        stop_price=setup.stop_loss.price,
        target_price=setup.take_profits[0].price,
        notional_value=setup.position_size.notional_value,
        duplicate_key=duplicate_key,
    )


def preview_execution(intent: ExecutionIntent, *, now: datetime | None = None) -> ExecutionResult:
    timestamp = now or datetime.now(UTC)
    order = ExecutionOrder(
        order_id=f"preview-{intent.duplicate_key}",
        intent=intent,
        state=ExecutionState.PREVIEW,
        created_at=timestamp,
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
        )
        append_audit_event(audit_log, result, timestamp=timestamp)
        return result
    order = ExecutionOrder(
        order_id=f"local-sim-{intent.duplicate_key}",
        intent=intent,
        state=ExecutionState.LOCAL_TESTNET_SIMULATED,
        created_at=timestamp,
    )
    result = ExecutionResult(
        state=ExecutionState.LOCAL_TESTNET_SIMULATED,
        order=order,
        reasons=(),
        audit_path=str(audit_log),
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
    )


def append_audit_event(path: Path, result: ExecutionResult, *, timestamp: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": timestamp.isoformat(),
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
