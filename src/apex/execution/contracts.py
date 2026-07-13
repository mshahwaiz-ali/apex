"""Immutable contracts for local execution simulation safety."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.strategies import TradeDirection


class ExecutionState(StrEnum):
    PREVIEW = "preview"
    REJECTED = "rejected"
    LOCAL_TESTNET_SIMULATED = "local_testnet_simulated"


class ExecutionEnvironment(StrEnum):
    LOCAL_TESTNET_SIMULATION = "local_testnet_simulation"


class KillSwitchState(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class ExecutionReconciliationStatus(StrEnum):
    MATCHED = "matched"
    MISSING_ADAPTER_ORDER = "missing_adapter_order"
    MISMATCHED = "mismatched"
    REJECTED_LOCAL = "rejected_local"


class ExecutionReadinessGateStatus(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


EXECUTION_AUDIT_SCHEMA_VERSION = 1
EXECUTION_RECONCILIATION_SCHEMA_VERSION = 1
EXECUTION_READINESS_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    enabled: bool = False
    testnet: bool = True
    environment: ExecutionEnvironment | str = ExecutionEnvironment.LOCAL_TESTNET_SIMULATION
    max_order_notional: float = 500.0
    daily_loss_limit: float = 100.0

    def __post_init__(self) -> None:
        try:
            environment = (
                self.environment
                if isinstance(self.environment, ExecutionEnvironment)
                else ExecutionEnvironment(str(self.environment))
            )
        except ValueError as exc:
            raise ValueError("execution environment must be local testnet simulation") from exc
        object.__setattr__(self, "environment", environment)
        for name in ("max_order_notional", "daily_loss_limit"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be positive and finite")
        if not self.testnet or environment is not ExecutionEnvironment.LOCAL_TESTNET_SIMULATION:
            raise ValueError("execution config only supports local testnet simulation")


@dataclass(frozen=True, slots=True)
class ExecutionIntent:
    symbol: str
    direction: TradeDirection
    quantity: float
    entry_price: float
    stop_price: float
    target_price: float
    notional_value: float
    duplicate_key: str
    target_prices: tuple[float, ...] = ()
    partial_close_percentages: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.duplicate_key.strip():
            raise ValueError("execution intent symbol and duplicate key cannot be empty")
        for name in ("quantity", "entry_price", "stop_price", "target_price", "notional_value"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be positive and finite")
        target_prices = self.target_prices or (self.target_price,)
        partials = self.partial_close_percentages or (100.0,)
        if len(target_prices) != len(partials):
            raise ValueError("execution target prices and partial close percentages must align")
        if not target_prices:
            raise ValueError("execution intent requires at least one target")
        for target in target_prices:
            if not math.isfinite(target) or target <= 0.0:
                raise ValueError("execution target prices must be positive and finite")
        for partial in partials:
            if not math.isfinite(partial) or partial <= 0.0:
                raise ValueError("execution partial close percentages must be positive and finite")
        if not math.isclose(sum(partials), 100.0, rel_tol=0.0, abs_tol=1e-6):
            raise ValueError("execution partial close percentages must sum to 100")
        if self.direction is TradeDirection.LONG:
            if any(target <= self.entry_price for target in target_prices):
                raise ValueError("long execution targets must be above entry")
            if tuple(sorted(target_prices)) != target_prices:
                raise ValueError("long execution targets must be ascending")
        else:
            if any(target >= self.entry_price for target in target_prices):
                raise ValueError("short execution targets must be below entry")
            if tuple(sorted(target_prices, reverse=True)) != target_prices:
                raise ValueError("short execution targets must be descending")
        object.__setattr__(self, "target_prices", target_prices)
        object.__setattr__(self, "partial_close_percentages", partials)


@dataclass(frozen=True, slots=True)
class ExecutionOrder:
    order_id: str
    intent: ExecutionIntent
    state: ExecutionState
    created_at: datetime
    environment: ExecutionEnvironment = ExecutionEnvironment.LOCAL_TESTNET_SIMULATION
    client_order_id: str | None = None
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.environment, ExecutionEnvironment):
            raise ValueError("execution order environment is invalid")
        if not self.order_id.strip():
            raise ValueError("execution order identity cannot be empty")
        if self.client_order_id is not None and not self.client_order_id.strip():
            raise ValueError("execution client order identity cannot be empty")
        if self.idempotency_key is not None and not self.idempotency_key.strip():
            raise ValueError("execution idempotency key cannot be empty")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("execution order time must be timezone-aware")
        if (
            self.state is ExecutionState.LOCAL_TESTNET_SIMULATED
            and self.environment is not ExecutionEnvironment.LOCAL_TESTNET_SIMULATION
        ):
            raise ValueError("simulated testnet orders require the local testnet environment")


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    state: ExecutionState
    order: ExecutionOrder | None
    reasons: tuple[str, ...]
    audit_path: str | None = None
    adapter_name: str = "local-simulation"

    def __post_init__(self) -> None:
        if self.state is ExecutionState.REJECTED:
            if self.order is not None or not self.reasons:
                raise ValueError("rejected execution requires reasons and no order")
        elif self.order is None:
            raise ValueError("non-rejected execution requires an order")


@dataclass(frozen=True, slots=True)
class ExecutionAdapterSnapshot:
    """Provider-independent order snapshot returned by a testnet adapter."""

    client_order_id: str
    order_id: str
    state: ExecutionState | str
    filled_quantity: float = 0.0
    average_fill_price: float | None = None

    def __post_init__(self) -> None:
        if not self.client_order_id.strip() or not self.order_id.strip():
            raise ValueError("adapter snapshot order identities cannot be empty")
        state = (
            self.state
            if isinstance(self.state, ExecutionState)
            else ExecutionState(str(self.state))
        )
        object.__setattr__(self, "state", state)
        if not math.isfinite(self.filled_quantity) or self.filled_quantity < 0.0:
            raise ValueError("adapter filled quantity must be finite and non-negative")
        if self.average_fill_price is not None and (
            not math.isfinite(self.average_fill_price) or self.average_fill_price <= 0.0
        ):
            raise ValueError("adapter average fill price must be positive and finite")


@dataclass(frozen=True, slots=True)
class ExecutionReconciliationRecord:
    """One reconciled audit event compared with an adapter snapshot."""

    status: ExecutionReconciliationStatus
    audit_state: ExecutionState
    client_order_id: str | None
    local_order_id: str | None
    adapter_order_id: str | None
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status is not ExecutionReconciliationStatus.MATCHED and not self.reasons:
            raise ValueError("non-matched reconciliation records require reasons")


@dataclass(frozen=True, slots=True)
class ExecutionReconciliationReport:
    """Deterministic reconciliation summary for local testnet simulation."""

    generated_at: datetime
    audit_path: str
    adapter_name: str
    total_audit_events: int
    matched_count: int
    missing_count: int
    mismatched_count: int
    rejected_local_count: int
    records: tuple[ExecutionReconciliationRecord, ...]

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("reconciliation report time must be timezone-aware")
        if not self.audit_path.strip() or not self.adapter_name.strip():
            raise ValueError("reconciliation report audit path and adapter name are required")
        if self.total_audit_events != len(self.records):
            raise ValueError("reconciliation total must match record count")
        expected = (
            self.matched_count
            + self.missing_count
            + self.mismatched_count
            + self.rejected_local_count
        )
        if expected != self.total_audit_events:
            raise ValueError("reconciliation counts must sum to total events")


@dataclass(frozen=True, slots=True)
class ExecutionReadinessGate:
    name: str
    status: ExecutionReadinessGateStatus
    detail: str

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.detail.strip():
            raise ValueError("readiness gate name and detail cannot be empty")


@dataclass(frozen=True, slots=True)
class ExecutionReadinessReport:
    """Execution readiness report with explicit local/exchange boundaries."""

    generated_at: datetime
    mode: str
    local_simulation_ready: bool
    exchange_ready: bool
    gates: tuple[ExecutionReadinessGate, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("readiness report time must be timezone-aware")
        if not self.mode.strip():
            raise ValueError("readiness mode cannot be empty")
        if not self.gates:
            raise ValueError("readiness report requires gates")
        if self.exchange_ready and self.blockers:
            raise ValueError("exchange-ready reports cannot include blockers")
