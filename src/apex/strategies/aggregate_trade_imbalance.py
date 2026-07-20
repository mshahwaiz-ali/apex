"""Read-only aggregate-trade imbalance diagnostics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.strategies.contracts import TradeDirection


class TradeImbalanceState(StrEnum):
    """Directional state derived from aggressive buy/sell notional."""

    SUPPORTIVE = "supportive"
    NEUTRAL = "neutral"
    CONTRADICTORY = "contradictory"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class AggregateTradeImbalancePolicy:
    """Thresholds for classifying aggressive-flow imbalance."""

    minimum_total_notional: float = 1.0
    supportive_ratio: float = 0.12
    contradictory_ratio: float = 0.12

    def __post_init__(self) -> None:
        if not math.isfinite(self.minimum_total_notional) or self.minimum_total_notional < 0:
            raise ValueError("minimum total notional must be finite and non-negative")
        for name, value in (
            ("supportive ratio", self.supportive_ratio),
            ("contradictory ratio", self.contradictory_ratio),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between zero and one")


@dataclass(frozen=True, slots=True)
class AggregateTradeImbalanceObservation:
    """Normalized aggressive-flow totals for one synchronized window."""

    aggressive_buy_notional: float
    aggressive_sell_notional: float
    trade_count: int
    window_seconds: int

    def __post_init__(self) -> None:
        for name, value in (
            ("aggressive buy notional", self.aggressive_buy_notional),
            ("aggressive sell notional", self.aggressive_sell_notional),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.trade_count < 0:
            raise ValueError("trade count cannot be negative")
        if self.window_seconds <= 0:
            raise ValueError("window seconds must be positive")


@dataclass(frozen=True, slots=True)
class AggregateTradeImbalanceAudit:
    """Read-only directional aggressive-flow assessment."""

    direction: TradeDirection
    state: TradeImbalanceState
    signed_imbalance_ratio: float
    total_notional: float
    trade_count: int
    window_seconds: int

    @property
    def usable(self) -> bool:
        return self.state is not TradeImbalanceState.INSUFFICIENT


def audit_aggregate_trade_imbalance(
    direction: TradeDirection,
    observation: AggregateTradeImbalanceObservation,
    *,
    policy: AggregateTradeImbalancePolicy,
) -> AggregateTradeImbalanceAudit:
    """Classify aggressive flow relative to the proposed trade direction."""

    total = observation.aggressive_buy_notional + observation.aggressive_sell_notional
    if total < policy.minimum_total_notional or observation.trade_count == 0:
        return AggregateTradeImbalanceAudit(
            direction=direction,
            state=TradeImbalanceState.INSUFFICIENT,
            signed_imbalance_ratio=0.0,
            total_notional=total,
            trade_count=observation.trade_count,
            window_seconds=observation.window_seconds,
        )

    raw_ratio = (observation.aggressive_buy_notional - observation.aggressive_sell_notional) / total
    signed_ratio = raw_ratio if direction is TradeDirection.LONG else -raw_ratio
    if signed_ratio >= policy.supportive_ratio:
        state = TradeImbalanceState.SUPPORTIVE
    elif signed_ratio <= -policy.contradictory_ratio:
        state = TradeImbalanceState.CONTRADICTORY
    else:
        state = TradeImbalanceState.NEUTRAL

    return AggregateTradeImbalanceAudit(
        direction=direction,
        state=state,
        signed_imbalance_ratio=signed_ratio,
        total_notional=total,
        trade_count=observation.trade_count,
        window_seconds=observation.window_seconds,
    )
