"""Read-only price/open-interest relationship diagnostics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.strategies.contracts import TradeDirection


class PriceOpenInterestState(StrEnum):
    """Interpretation of synchronized price and open-interest changes."""

    NEW_POSITION_CONFIRMATION = "new_position_confirmation"
    SHORT_COVERING_OR_LONG_LIQUIDATION = "short_covering_or_long_liquidation"
    POSITION_BUILD_AGAINST_MOVE = "position_build_against_move"
    LOW_PARTICIPATION = "low_participation"
    NEUTRAL = "neutral"


@dataclass(frozen=True, slots=True)
class PriceOpenInterestPolicy:
    """Materiality thresholds for price/OI interpretation."""

    minimum_price_change_fraction: float = 0.001
    minimum_open_interest_change_fraction: float = 0.01

    def __post_init__(self) -> None:
        for name, value in (
            ("minimum price change fraction", self.minimum_price_change_fraction),
            (
                "minimum open-interest change fraction",
                self.minimum_open_interest_change_fraction,
            ),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class PriceOpenInterestObservation:
    """Synchronized before/after price and open-interest values."""

    start_price: float
    end_price: float
    start_open_interest: float
    end_open_interest: float
    window_seconds: int

    def __post_init__(self) -> None:
        for name, value in (
            ("start price", self.start_price),
            ("end price", self.end_price),
            ("start open interest", self.start_open_interest),
            ("end open interest", self.end_open_interest),
        ):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        if self.window_seconds <= 0:
            raise ValueError("window seconds must be positive")


@dataclass(frozen=True, slots=True)
class PriceOpenInterestAudit:
    """Read-only price/OI relationship result."""

    direction: TradeDirection
    state: PriceOpenInterestState
    signed_price_change_fraction: float
    open_interest_change_fraction: float
    window_seconds: int


def audit_price_open_interest(
    direction: TradeDirection,
    observation: PriceOpenInterestObservation,
    *,
    policy: PriceOpenInterestPolicy,
) -> PriceOpenInterestAudit:
    """Classify whether participation confirms or contradicts the proposed side."""

    raw_price_change = (observation.end_price - observation.start_price) / observation.start_price
    signed_price_change = (
        raw_price_change if direction is TradeDirection.LONG else -raw_price_change
    )
    oi_change = (
        observation.end_open_interest - observation.start_open_interest
    ) / observation.start_open_interest

    price_material = abs(signed_price_change) >= policy.minimum_price_change_fraction
    oi_material = abs(oi_change) >= policy.minimum_open_interest_change_fraction

    if not price_material and not oi_material:
        state = PriceOpenInterestState.NEUTRAL
    elif signed_price_change > 0 and oi_change > 0 and oi_material:
        state = PriceOpenInterestState.NEW_POSITION_CONFIRMATION
    elif signed_price_change > 0 and oi_change < 0 and oi_material:
        state = PriceOpenInterestState.SHORT_COVERING_OR_LONG_LIQUIDATION
    elif signed_price_change < 0 and oi_change > 0 and oi_material:
        state = PriceOpenInterestState.POSITION_BUILD_AGAINST_MOVE
    elif price_material and not oi_material:
        state = PriceOpenInterestState.LOW_PARTICIPATION
    else:
        state = PriceOpenInterestState.NEUTRAL

    return PriceOpenInterestAudit(
        direction=direction,
        state=state,
        signed_price_change_fraction=signed_price_change,
        open_interest_change_fraction=oi_change,
        window_seconds=observation.window_seconds,
    )
