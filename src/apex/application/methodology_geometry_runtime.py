"""Authoritative runtime measurements for shadow geometry safety."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median
from typing import cast

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
    limit_entry_fee_pct: float | None = None
    limit_exit_fee_pct: float | None = None
    limit_entry_slippage_pct: float | None = None
    limit_exit_slippage_pct: float | None = None
    include_observed_spread_in_cost: bool = False

    def __post_init__(self) -> None:
        values = (
            ("entry fee percentage", self.entry_fee_pct),
            ("exit fee percentage", self.exit_fee_pct),
            ("entry slippage percentage", self.entry_slippage_pct),
            ("exit slippage percentage", self.exit_slippage_pct),
            ("limit entry fee percentage", self.limit_entry_fee_pct),
            ("limit exit fee percentage", self.limit_exit_fee_pct),
            ("limit entry slippage percentage", self.limit_entry_slippage_pct),
            ("limit exit slippage percentage", self.limit_exit_slippage_pct),
        )
        for name, value in values:
            if value is not None and (not math.isfinite(value) or value < 0.0):
                raise ValueError(f"{name} must be finite and non-negative")
        if any(value is not None for _, value in values[4:]) and any(
            value is None for _, value in values[4:]
        ):
            raise ValueError("limit execution-cost profile must be complete")

    @property
    def total_pct(self) -> float:
        return self.total_pct_for("market")

    def total_pct_for(self, profile: str) -> float:
        if profile == "limit" and self.limit_entry_fee_pct is not None:
            assert self.limit_exit_fee_pct is not None
            assert self.limit_entry_slippage_pct is not None
            assert self.limit_exit_slippage_pct is not None
            return (
                self.limit_entry_fee_pct
                + self.limit_exit_fee_pct
                + self.limit_entry_slippage_pct
                + self.limit_exit_slippage_pct
            )
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
        return self.expected_cost_pct_for("market")

    def expected_cost_pct_for(self, profile: str) -> float | None:
        if self.execution_costs is None:
            return None
        spread = (
            self.observed_spread_pct
            if self.execution_costs.include_observed_spread_in_cost
            else 0.0
        )
        return self.execution_costs.total_pct_for(profile) + spread


DEFAULT_EXECUTION_BUFFER_POLICY = ExecutionBufferPolicy(
    atr_multiplier=0.25,
    spread_multiplier=1.0,
    minimum_buffer=0.0,
)

_TIMEFRAME_ATR_BUFFER_MULTIPLIERS: dict[str, float] = {
    "1m": 0.50,
    "3m": 0.45,
    "5m": 0.40,
    "15m": 0.34,
    "30m": 0.30,
    "1h": 0.27,
    "4h": 0.24,
}


def execution_buffer_policy_for_timeframe(
    timeframe: str,
    *,
    recent_noise_floor: float = 0.0,
) -> ExecutionBufferPolicy:
    """Return a deterministic volatility policy for one decision timeframe."""

    multiplier = _TIMEFRAME_ATR_BUFFER_MULTIPLIERS.get(
        timeframe,
        DEFAULT_EXECUTION_BUFFER_POLICY.atr_multiplier,
    )
    return ExecutionBufferPolicy(
        atr_multiplier=multiplier,
        spread_multiplier=DEFAULT_EXECUTION_BUFFER_POLICY.spread_multiplier,
        minimum_buffer=max(0.0, recent_noise_floor),
    )


def recent_execution_noise_floor(context: StrategyContext) -> float:
    """Estimate ordinary wick/range noise from recent closed candles."""

    frame: object = context.decision_frame
    recent_value: object = getattr(frame, "recent_candles", ())
    if not isinstance(recent_value, (tuple, list)) or not recent_value:
        return 0.0

    ranges: list[float] = []
    wick_depths: list[float] = []

    for candle in recent_value[-12:]:
        open_value: object = getattr(candle, "open", None)
        high_value: object = getattr(candle, "high", None)
        low_value: object = getattr(candle, "low", None)
        close_value: object = getattr(candle, "close", None)

        values = (open_value, high_value, low_value, close_value)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
            continue

        candle_open = float(cast(int | float, open_value))
        candle_high = float(cast(int | float, high_value))
        candle_low = float(cast(int | float, low_value))
        candle_close = float(cast(int | float, close_value))

        ranges.append(max(0.0, candle_high - candle_low))
        wick_depths.append(
            max(
                0.0,
                candle_high - max(candle_open, candle_close),
                min(candle_open, candle_close) - candle_low,
            )
        )

    if not ranges or not wick_depths:
        return 0.0

    features: object = getattr(frame, "features", None)
    atr_value: object = getattr(features, "atr", None)
    if isinstance(atr_value, bool) or not isinstance(atr_value, (int, float)):
        return 0.0

    atr = float(atr_value)
    if not math.isfinite(atr) or atr <= 0.0:
        return 0.0

    median_range = float(median(ranges))
    median_wick = float(median(wick_depths))
    raw_floor = max(median_wick, median_range * 0.30)

    return min(raw_floor, atr * 0.75)


def geometry_execution_costs_from_settings(
    settings: GeometryExecutionSettings,
) -> GeometryExecutionCosts | None:
    """Resolve costs only when configuration is enabled and complete."""

    if not settings.enabled:
        return None

    market = settings.market
    if market is None:
        assert settings.entry_fee_pct is not None
        assert settings.exit_fee_pct is not None
        assert settings.entry_slippage_pct is not None
        assert settings.exit_slippage_pct is not None
        market_values = (
            settings.entry_fee_pct,
            settings.exit_fee_pct,
            settings.entry_slippage_pct,
            settings.exit_slippage_pct,
        )
    else:
        market_values = (
            market.entry_fee_pct,
            market.exit_fee_pct,
            market.entry_slippage_pct,
            market.exit_slippage_pct,
        )

    limit = settings.limit
    return GeometryExecutionCosts(
        entry_fee_pct=market_values[0],
        exit_fee_pct=market_values[1],
        entry_slippage_pct=market_values[2],
        exit_slippage_pct=market_values[3],
        limit_entry_fee_pct=None if limit is None else limit.entry_fee_pct,
        limit_exit_fee_pct=None if limit is None else limit.exit_fee_pct,
        limit_entry_slippage_pct=None if limit is None else limit.entry_slippage_pct,
        limit_exit_slippage_pct=None if limit is None else limit.exit_slippage_pct,
        include_observed_spread_in_cost=settings.include_observed_spread_in_cost,
    )


def build_geometry_runtime_context(
    context: StrategyContext,
    *,
    execution_costs: GeometryExecutionCosts | None = None,
    buffer_policy: ExecutionBufferPolicy | None = None,
) -> GeometryRuntimeContext:
    """Build one shared geometry context from the canonical decision frame."""

    frame = context.decision_frame
    noise_floor = recent_execution_noise_floor(context)
    timeframe_value: object = getattr(frame, "timeframe", "")
    timeframe = timeframe_value if isinstance(timeframe_value, str) else ""
    resolved_policy = buffer_policy or execution_buffer_policy_for_timeframe(
        timeframe,
        recent_noise_floor=noise_floor,
    )
    spread, spread_source = _observed_spread(
        frame.spread_percentage, frame.order_book_spread_percentage
    )
    spread_distance = frame.current_price * spread / 100.0
    buffer = derive_execution_buffer(
        atr=frame.features.atr,
        spread=spread_distance,
        policy=resolved_policy,
    )
    return GeometryRuntimeContext(
        decision_atr=frame.features.atr,
        observed_spread_pct=spread,
        execution_buffer=buffer.execution_buffer,
        execution_costs=execution_costs,
        spread_source=spread_source,
        buffer_reason=(
            "execution buffer derived from timeframe-specific ATR, observed spread, "
            "and recent closed-candle noise floor"
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
    "execution_buffer_policy_for_timeframe",
    "geometry_execution_costs_from_settings",
    "recent_execution_noise_floor",
]
