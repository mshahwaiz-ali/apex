"""Immutable contracts for deterministic Phase 6 risk analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.strategies.contracts import StrategyType, TradeDirection


class RiskDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class RiskRejectionCode(StrEnum):
    NO_SELECTED_CANDIDATE = "no_selected_candidate"
    ENTRY_TOO_EXTENDED = "entry_too_extended"
    STOP_TOO_TIGHT = "stop_too_tight"
    STOP_TOO_WIDE = "stop_too_wide"
    INSUFFICIENT_TARGET_SPACE = "insufficient_target_space"
    LEVERAGE_UNSAFE = "leverage_unsafe"
    MAX_CONCURRENT_TRADES = "max_concurrent_trades"
    MAX_OPEN_RISK = "max_open_risk"
    MAX_DIRECTIONAL_RISK = "max_directional_risk"
    MAX_CORRELATED_RISK = "max_correlated_risk"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    CONSECUTIVE_LOSS_LIMIT = "consecutive_loss_limit"


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _positive(name: str, value: float) -> None:
    _finite(name, value)
    if value <= 0.0:
        raise ValueError(f"{name} must be greater than zero")


@dataclass(frozen=True, slots=True)
class ActionableEntry:
    lower: float
    upper: float
    preferred: float
    current_price: float
    maximum_chase_price: float
    current_price_inside_zone: bool

    def __post_init__(self) -> None:
        for name, value in (
            ("entry lower", self.lower),
            ("entry upper", self.upper),
            ("preferred entry", self.preferred),
            ("current price", self.current_price),
            ("maximum chase price", self.maximum_chase_price),
        ):
            _positive(name, value)
        if self.lower > self.upper:
            raise ValueError("entry lower cannot exceed entry upper")
        if not self.lower <= self.preferred <= self.upper:
            raise ValueError("preferred entry must lie inside the entry zone")


@dataclass(frozen=True, slots=True)
class StopLoss:
    price: float
    distance: float
    distance_pct: float
    rationale: tuple[str, ...]

    def __post_init__(self) -> None:
        _positive("stop price", self.price)
        _positive("stop distance", self.distance)
        _positive("stop distance percentage", self.distance_pct)
        if not self.rationale:
            raise ValueError("stop rationale cannot be empty")


@dataclass(frozen=True, slots=True)
class TakeProfit:
    label: str
    price: float
    reward: float
    risk_reward: float
    rationale: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("target label cannot be empty")
        for name, value in (
            ("target price", self.price),
            ("target reward", self.reward),
            ("target risk reward", self.risk_reward),
        ):
            _positive(name, value)
        if not self.rationale:
            raise ValueError("target rationale cannot be empty")


@dataclass(frozen=True, slots=True)
class PositionSize:
    risk_amount: float
    quantity: float
    notional_value: float
    account_risk_pct: float
    required_leverage: float

    def __post_init__(self) -> None:
        for name, value in (
            ("risk amount", self.risk_amount),
            ("position quantity", self.quantity),
            ("position notional", self.notional_value),
            ("account risk percentage", self.account_risk_pct),
            ("required leverage", self.required_leverage),
        ):
            _positive(name, value)


@dataclass(frozen=True, slots=True)
class LeverageRange:
    minimum: float
    maximum: float
    modeled_maximum: float
    liquidation_price_at_maximum: float
    stop_to_liquidation_buffer_pct: float

    def __post_init__(self) -> None:
        for name, value in (
            ("minimum leverage", self.minimum),
            ("maximum leverage", self.maximum),
            ("modeled maximum leverage", self.modeled_maximum),
            ("liquidation price", self.liquidation_price_at_maximum),
            ("stop to liquidation buffer percentage", self.stop_to_liquidation_buffer_pct),
        ):
            _positive(name, value)
        if self.minimum > self.maximum:
            raise ValueError("minimum leverage cannot exceed maximum leverage")
        if self.maximum > self.modeled_maximum:
            raise ValueError("recommended leverage cannot exceed modeled maximum leverage")


@dataclass(frozen=True, slots=True)
class RiskApprovedSetup:
    symbol: str
    direction: TradeDirection
    strategy: StrategyType
    decision_time: datetime
    candidate_id: str
    confidence_score: float
    entry: ActionableEntry
    stop_loss: StopLoss
    take_profits: tuple[TakeProfit, ...]
    position_size: PositionSize
    leverage: LeverageRange
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.candidate_id.strip():
            raise ValueError("symbol and candidate identity cannot be empty")
        if self.decision_time.tzinfo is None or self.decision_time.utcoffset() is None:
            raise ValueError("decision time must be timezone-aware")
        _finite("confidence score", self.confidence_score)
        if not 0.0 <= self.confidence_score <= 100.0:
            raise ValueError("confidence score must be between zero and 100")
        if not self.take_profits:
            raise ValueError("approved setup requires at least one target")
        if self.position_size.required_leverage > self.leverage.maximum:
            raise ValueError("position sizing cannot require unsafe leverage")
        if self.direction is TradeDirection.LONG:
            if self.stop_loss.price >= self.entry.lower:
                raise ValueError("long stop must be below the entry zone")
            if any(target.price <= self.entry.upper for target in self.take_profits):
                raise ValueError("long targets must be above the entry zone")
            if self.leverage.liquidation_price_at_maximum >= self.stop_loss.price:
                raise ValueError("long liquidation must remain below the stop")
        else:
            if self.stop_loss.price <= self.entry.upper:
                raise ValueError("short stop must be above the entry zone")
            if any(target.price >= self.entry.lower for target in self.take_profits):
                raise ValueError("short targets must be below the entry zone")
            if self.leverage.liquidation_price_at_maximum <= self.stop_loss.price:
                raise ValueError("short liquidation must remain above the stop")


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    symbol: str
    decision_time: datetime
    decision: RiskDecision
    setup: RiskApprovedSetup | None
    rejection_codes: tuple[RiskRejectionCode, ...]
    reasons: tuple[str, ...]
    configuration_id: str

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.configuration_id.strip():
            raise ValueError("symbol and configuration identifier cannot be empty")
        if self.decision_time.tzinfo is None or self.decision_time.utcoffset() is None:
            raise ValueError("decision time must be timezone-aware")
        if len(set(self.rejection_codes)) != len(self.rejection_codes):
            raise ValueError("rejection codes must be unique")
        if self.decision is RiskDecision.APPROVED:
            if self.setup is None or self.rejection_codes or self.reasons:
                raise ValueError("approved assessment must contain only an approved setup")
        elif self.setup is not None or not self.rejection_codes or not self.reasons:
            raise ValueError("rejected assessment requires rejection codes and reasons")
        if len(self.rejection_codes) != len(self.reasons):
            raise ValueError("rejection codes and reasons must align")
