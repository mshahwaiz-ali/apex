"""Authoritative runtime measurements for shadow geometry safety."""

from __future__ import annotations

import math
from dataclasses import dataclass

from apex.config.settings import GeometryExecutionSettings
from apex.strategies.context import StrategyContext
from apex.strategies.geometry_audit import (
    ExecutionBufferPolicy,
    derive_execution_buffer,
)


@dataclass(frozen=True, slots=True)
class GeometryExecutionCosts:
    """Explicit round-trip execution-cost assumptions in percentage points."""

    entry_fee_pct: float
    exit_fee_pct: float
    entry_slippage_pct: float
    exit_slippage_pct: float

    def __post_init__(self) -> None:
        for name, value in (
            ("entry fee percentage", self.entry_fee_pct),
            ("exit fee percentage", self.exit_fee_pct),
            ("entry slippage percentage", self.entry_slippage_pct),
            ("exit slippage percentage", self.exit_slippage_pct),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")

    @property
    def total_pct(self) -> float:
        return (
            self.entry_fee_pct
            + self.exit_fee_pct
            + self.entry_slippage_pct
            + self.exit_slippage_pct
        )


@dataclass(frozen=True, slots=True)
class GeometryRuntimeContext:
    """Observed market measurements plus explicit execution assumptions."""

    decision_atr: float
    observed_spread_pct: float
    execution_buffer: float
    execution_costs: GeometryExecutionCosts | None
    spread_source: str
    buffer_reason: str

    def __post_init__(self) -> None:
        for name, value in (
            ("decision ATR", self.decision_atr),
            ("observed spread percentage", self.observed_spread_pct),
            ("execution buffer", self.execution_buffer),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.decision_atr <= 0.0:
            raise ValueError("decision ATR must be positive")
        if not self.spread_source.strip():
            raise ValueError("spread source cannot be empty")
        if not self.buffer_reason.strip():
            raise ValueError("buffer reason cannot be empty")

    @property
    def expected_cost_pct(self) -> float | None:
        if self.execution_costs is None:
            return None
        return self.execution_costs.total_pct + self.observed_spread_pct


DEFAULT_EXECUTION_BUFFER_POLICY = ExecutionBufferPolicy(
    atr_multiplier=0.25,
    spread_multiplier=1.0,
    minimum_buffer=0.0,
)


def geometry_execution_costs_from_settings(
    settings: GeometryExecutionSettings,
) -> GeometryExecutionCosts | None:
    """Resolve costs only when configuration is enabled and complete."""

    if not settings.enabled:
        return None
    assert settings.entry_fee_pct is not None
    assert settings.exit_fee_pct is not None
    assert settings.entry_slippage_pct is not None
    assert settings.exit_slippage_pct is not None
    return GeometryExecutionCosts(
        entry_fee_pct=settings.entry_fee_pct,
        exit_fee_pct=settings.exit_fee_pct,
        entry_slippage_pct=settings.entry_slippage_pct,
        exit_slippage_pct=settings.exit_slippage_pct,
    )


def build_geometry_runtime_context(
    context: StrategyContext,
    *,
    execution_costs: GeometryExecutionCosts | None = None,
    buffer_policy: ExecutionBufferPolicy = DEFAULT_EXECUTION_BUFFER_POLICY,
) -> GeometryRuntimeContext:
    """Build one shared geometry context from the canonical decision frame."""

    frame = context.decision_frame
    spread, spread_source = _observed_spread(
        frame.spread_percentage, frame.order_book_spread_percentage
    )
    spread_distance = frame.current_price * spread / 100.0
    buffer = derive_execution_buffer(
        atr=frame.features.atr,
        spread=spread_distance,
        policy=buffer_policy,
    )
    return GeometryRuntimeContext(
        decision_atr=frame.features.atr,
        observed_spread_pct=spread,
        execution_buffer=buffer.execution_buffer,
        execution_costs=execution_costs,
        spread_source=spread_source,
        buffer_reason=(
            "execution buffer derived from the larger of observed ATR and spread "
            "components under the shared runtime policy"
        ),
    )


def _observed_spread(
    ticker_spread_pct: float | None,
    order_book_spread_pct: float | None,
) -> tuple[float, str]:
    available = tuple(
        (name, value)
        for name, value in (
            ("ticker", ticker_spread_pct),
            ("order_book", order_book_spread_pct),
        )
        if value is not None
    )
    if not available:
        return 0.0, "unavailable"
    source, value = max(available, key=lambda item: item[1])
    assert value is not None
    return value, source


__all__ = [
    "DEFAULT_EXECUTION_BUFFER_POLICY",
    "GeometryExecutionCosts",
    "GeometryRuntimeContext",
    "build_geometry_runtime_context",
    "geometry_execution_costs_from_settings",
]
