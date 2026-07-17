"""Volatility-aware near-CMP entry-location selection."""

from __future__ import annotations

import math
from dataclasses import dataclass

from apex.strategies.contracts import EntryMode, EntryZone, TradeDirection


@dataclass(frozen=True, slots=True)
class EntryReference:
    """A strategy-provided nearby location considered by the shared engine."""

    price: float
    mode: EntryMode
    rationale: tuple[str, ...]
    scaled: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(self.price) or self.price <= 0:
            raise ValueError("entry-reference price must be positive and finite")
        if not self.rationale:
            raise ValueError("entry-reference rationale cannot be empty")


@dataclass(frozen=True, slots=True)
class EntrySelectionConfig:
    """Configurable limits used by all strategy analysis strategies."""

    max_percentage_distance: float = 0.012
    max_atr_distance: float = 0.8
    scaled_half_width_atr: float = 0.06
    minimum_risk_reward_improvement: float = 0.15
    default_expiry_seconds: int = 900

    def __post_init__(self) -> None:
        for name, value in (
            ("maximum percentage distance", self.max_percentage_distance),
            ("maximum ATR distance", self.max_atr_distance),
            ("scaled half-width ATR", self.scaled_half_width_atr),
            ("minimum risk-reward improvement", self.minimum_risk_reward_improvement),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.max_percentage_distance == 0 and self.max_atr_distance == 0:
            raise ValueError("at least one entry-distance limit must be positive")
        if self.default_expiry_seconds <= 0:
            raise ValueError("default expiry must be positive")


DEFAULT_ENTRY_SELECTION_CONFIG = EntrySelectionConfig()


def select_entry_zone(
    *,
    current_price: float,
    atr: float,
    direction: TradeDirection,
    invalidation_price: float,
    target_price: float,
    references: tuple[EntryReference, ...] = (),
    config: EntrySelectionConfig = DEFAULT_ENTRY_SELECTION_CONFIG,
) -> EntryZone:
    """Return the best actionable entry while rejecting unjustified waiting."""

    _validate_market_geometry(
        current_price=current_price,
        atr=atr,
        direction=direction,
        invalidation_price=invalidation_price,
        target_price=target_price,
    )
    market = _build_zone(
        current_price=current_price,
        preferred=current_price,
        atr=atr,
        direction=direction,
        mode=EntryMode.MARKET_NEAR,
        rationale=("current price is technically valid and immediately actionable",),
        scaled=False,
        config=config,
    )
    market_rr = _risk_reward(
        price=current_price,
        invalidation_price=invalidation_price,
        target_price=target_price,
    )
    eligible: list[tuple[EntryZone, float]] = [(market, market_rr)]
    for reference in references:
        distance = abs(reference.price - current_price)
        allowed_distance = max(
            current_price * config.max_percentage_distance,
            atr * config.max_atr_distance,
        )
        if distance > allowed_distance:
            continue
        if not _entry_is_directionally_valid(
            price=reference.price,
            direction=direction,
            invalidation_price=invalidation_price,
            target_price=target_price,
        ):
            continue
        zone = _build_zone(
            current_price=current_price,
            preferred=reference.price,
            atr=atr,
            direction=direction,
            mode=EntryMode.SCALED_ENTRY if reference.scaled else reference.mode,
            rationale=reference.rationale,
            scaled=reference.scaled,
            config=config,
        )
        if not _zone_is_directionally_valid(
            zone=zone,
            direction=direction,
            invalidation_price=invalidation_price,
            target_price=target_price,
        ):
            continue
        reference_rr = _risk_reward(
            price=reference.price,
            invalidation_price=invalidation_price,
            target_price=target_price,
        )
        improvement = (reference_rr - market_rr) / market_rr if market_rr > 0 else 0.0
        if distance > 0 and improvement < config.minimum_risk_reward_improvement:
            continue
        eligible.append((zone, reference_rr))

    return min(
        eligible,
        key=lambda item: (
            -item[1],
            item[0].distance_from_current,
            -item[0].location_quality,
            item[0].mode.value,
        ),
    )[0]


def _build_zone(
    *,
    current_price: float,
    preferred: float,
    atr: float,
    direction: TradeDirection,
    mode: EntryMode,
    rationale: tuple[str, ...],
    scaled: bool,
    config: EntrySelectionConfig,
) -> EntryZone:
    distance = abs(preferred - current_price)
    percentage_distance = distance / current_price
    atr_distance = distance / atr
    allowed_distance = max(
        current_price * config.max_percentage_distance,
        atr * config.max_atr_distance,
    )
    max_chase_price = (
        current_price + allowed_distance
        if direction is TradeDirection.LONG
        else current_price - allowed_distance
    )
    location_quality = max(0.0, 1.0 - distance / allowed_distance)
    half_width = atr * config.scaled_half_width_atr if scaled else 0.0
    return EntryZone(
        lower=preferred - half_width,
        upper=preferred + half_width,
        preferred=preferred,
        current_price=current_price,
        distance_from_current=percentage_distance,
        atr_distance=atr_distance,
        estimated_move_missed=percentage_distance,
        location_quality=location_quality,
        mode=mode,
        rationale=rationale,
        is_extended=atr_distance > config.max_atr_distance,
        max_chase_price=max_chase_price,
        expires_after_seconds=config.default_expiry_seconds,
    )


def _validate_market_geometry(
    *,
    current_price: float,
    atr: float,
    direction: TradeDirection,
    invalidation_price: float,
    target_price: float,
) -> None:
    for name, value in (
        ("current price", current_price),
        ("ATR", atr),
        ("invalidation price", invalidation_price),
        ("target price", target_price),
    ):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be positive and finite")
    if direction is TradeDirection.LONG:
        if not invalidation_price < current_price < target_price:
            raise ValueError("long geometry requires invalidation below CMP and target above CMP")
    elif not target_price < current_price < invalidation_price:
        raise ValueError("short geometry requires target below CMP and invalidation above CMP")


def _entry_is_directionally_valid(
    *,
    price: float,
    direction: TradeDirection,
    invalidation_price: float,
    target_price: float,
) -> bool:
    if direction is TradeDirection.LONG:
        return invalidation_price < price < target_price
    return target_price < price < invalidation_price


def _zone_is_directionally_valid(
    *,
    zone: EntryZone,
    direction: TradeDirection,
    invalidation_price: float,
    target_price: float,
) -> bool:
    if direction is TradeDirection.LONG:
        return invalidation_price < zone.lower and zone.upper < target_price
    return target_price < zone.lower and zone.upper < invalidation_price


def _risk_reward(*, price: float, invalidation_price: float, target_price: float) -> float:
    risk = abs(price - invalidation_price)
    reward = abs(target_price - price)
    return reward / risk if risk > 0 else 0.0
