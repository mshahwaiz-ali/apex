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
    zone_lower: float | None = None
    zone_upper: float | None = None
    trigger_price: float | None = None
    max_chase_price: float | None = None
    expires_after_seconds: int | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.price) or self.price <= 0:
            raise ValueError("entry-reference price must be positive and finite")
        if not self.rationale:
            raise ValueError("entry-reference rationale cannot be empty")
        for name, value in (
            ("entry-reference zone lower", self.zone_lower),
            ("entry-reference zone upper", self.zone_upper),
            ("entry-reference trigger", self.trigger_price),
            ("entry-reference maximum chase", self.max_chase_price),
        ):
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be positive and finite when provided")
        if (self.zone_lower is None) is not (self.zone_upper is None):
            raise ValueError("entry-reference zone bounds must be provided together")
        if self.zone_lower is not None and self.zone_upper is not None:
            if self.zone_lower > self.zone_upper:
                raise ValueError("entry-reference zone lower cannot exceed zone upper")
            if not self.zone_lower <= self.price <= self.zone_upper:
                raise ValueError("entry-reference price must lie inside explicit zone")
        if self.expires_after_seconds is not None and self.expires_after_seconds <= 0:
            raise ValueError("entry-reference expiry must be positive when provided")


@dataclass(frozen=True, slots=True)
class EntrySelectionConfig:
    """Configurable limits used by all strategy analysis strategies."""

    max_percentage_distance: float = 0.012
    max_atr_distance: float = 0.8
    scaled_half_width_atr: float = 0.06
    reference_half_width_atr: float = 0.03
    market_half_width_atr: float = 0.01
    market_tick_multiple: float = 1.0
    market_spread_multiplier: float = 0.5
    minimum_risk_reward_improvement: float = 0.15
    default_expiry_seconds: int = 900

    def __post_init__(self) -> None:
        for name, value in (
            ("maximum percentage distance", self.max_percentage_distance),
            ("maximum ATR distance", self.max_atr_distance),
            ("scaled half-width ATR", self.scaled_half_width_atr),
            ("reference half-width ATR", self.reference_half_width_atr),
            ("market half-width ATR", self.market_half_width_atr),
            ("market tick multiple", self.market_tick_multiple),
            ("market spread multiplier", self.market_spread_multiplier),
            ("minimum risk-reward improvement", self.minimum_risk_reward_improvement),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.max_percentage_distance == 0 and self.max_atr_distance == 0:
            raise ValueError("at least one entry-distance limit must be positive")
        if self.default_expiry_seconds <= 0:
            raise ValueError("default expiry must be positive")


DEFAULT_ENTRY_SELECTION_CONFIG = EntrySelectionConfig()


def find_entry_zones(
    *,
    current_price: float,
    atr: float,
    direction: TradeDirection,
    invalidation_price: float,
    target_price: float,
    references: tuple[EntryReference, ...] = (),
    config: EntrySelectionConfig = DEFAULT_ENTRY_SELECTION_CONFIG,
    allow_market_entry: bool = True,
    tick_size: float | None = None,
    spread_percentage: float | None = None,
) -> tuple[EntryZone, ...]:
    """Return every eligible entry opportunity in deterministic preference order."""

    _validate_market_geometry(
        current_price=current_price,
        atr=atr,
        direction=direction,
        invalidation_price=invalidation_price,
        target_price=target_price,
    )
    _validate_execution_tolerance_inputs(
        tick_size=tick_size,
        spread_percentage=spread_percentage,
    )
    market = _build_zone(
        current_price=current_price,
        preferred=current_price,
        atr=atr,
        direction=direction,
        invalidation_price=invalidation_price,
        target_price=target_price,
        mode=EntryMode.MARKET_NEAR,
        rationale=("current price is technically valid and immediately actionable",),
        scaled=False,
        config=config,
        tick_size=tick_size,
        spread_percentage=spread_percentage,
    )
    market_rr = _risk_reward(
        price=current_price,
        invalidation_price=invalidation_price,
        target_price=target_price,
    )
    eligible: list[tuple[EntryZone, float]] = []
    if allow_market_entry:
        eligible.append((market, market_rr))
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
            invalidation_price=invalidation_price,
            target_price=target_price,
            mode=EntryMode.SCALED_ENTRY if reference.scaled else reference.mode,
            rationale=reference.rationale,
            scaled=reference.scaled,
            config=config,
            explicit_lower=reference.zone_lower,
            explicit_upper=reference.zone_upper,
            explicit_max_chase=reference.max_chase_price,
            explicit_expiry_seconds=reference.expires_after_seconds,
            tick_size=tick_size,
            spread_percentage=spread_percentage,
        )
        if not _maximum_chase_is_directionally_valid(zone=zone, direction=direction):
            raise AssertionError("entry-zone construction returned an invalid chase boundary")
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

    if not eligible:
        raise ValueError(
            "no confirmed current-price entry or eligible nearby entry reference is available"
        )

    ranked = sorted(
        eligible,
        key=lambda item: (
            -item[1],
            item[0].distance_from_current,
            -item[0].location_quality,
            item[0].mode.value,
            item[0].preferred,
        ),
    )
    unique: list[EntryZone] = []
    seen: set[tuple[float, float, float, EntryMode]] = set()
    for zone, _ in ranked:
        key = (
            round(zone.lower, 12),
            round(zone.upper, 12),
            round(zone.preferred, 12),
            zone.mode,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(zone)
    return tuple(unique)


def select_entry_zone(
    *,
    current_price: float,
    atr: float,
    direction: TradeDirection,
    invalidation_price: float,
    target_price: float,
    references: tuple[EntryReference, ...] = (),
    config: EntrySelectionConfig = DEFAULT_ENTRY_SELECTION_CONFIG,
    allow_market_entry: bool = True,
    tick_size: float | None = None,
    spread_percentage: float | None = None,
) -> EntryZone:
    """Return the preferred entry while preserving multi-entry search separately."""

    return find_entry_zones(
        current_price=current_price,
        atr=atr,
        direction=direction,
        invalidation_price=invalidation_price,
        target_price=target_price,
        references=references,
        config=config,
        allow_market_entry=allow_market_entry,
        tick_size=tick_size,
        spread_percentage=spread_percentage,
    )[0]


def _build_zone(
    *,
    current_price: float,
    preferred: float,
    atr: float,
    direction: TradeDirection,
    invalidation_price: float,
    target_price: float,
    mode: EntryMode,
    rationale: tuple[str, ...],
    scaled: bool,
    config: EntrySelectionConfig,
    explicit_lower: float | None = None,
    explicit_upper: float | None = None,
    explicit_max_chase: float | None = None,
    explicit_expiry_seconds: int | None = None,
    tick_size: float | None = None,
    spread_percentage: float | None = None,
) -> EntryZone:
    distance = abs(preferred - current_price)
    percentage_distance = distance / current_price
    atr_distance = distance / atr
    base_distance = max(
        current_price * config.max_percentage_distance, atr * config.max_atr_distance
    )
    risk = abs(preferred - invalidation_price)
    reward = abs(target_price - preferred)
    minimum_remaining_reward = risk * 1.1
    reward_room_distance = max(0.0, reward - minimum_remaining_reward)
    structure_room_distance = max(0.0, abs(target_price - preferred) * 0.65)
    allowed_distance = min(
        base_distance,
        max(reward_room_distance, 0.0),
        max(structure_room_distance, 0.0),
    )
    market_half_width = min(
        max(
            atr * config.market_half_width_atr,
            0.0 if tick_size is None else tick_size * config.market_tick_multiple,
            (
                0.0
                if spread_percentage is None
                else current_price * spread_percentage / 100.0 * config.market_spread_multiplier
            ),
        ),
        min(risk, reward) * 0.25,
    )
    half_width = (
        atr * config.scaled_half_width_atr
        if scaled
        else atr * config.reference_half_width_atr
        if mode is not EntryMode.MARKET_NEAR
        else market_half_width
    )
    allowed_distance = max(allowed_distance, half_width)
    derived_max_chase = (
        preferred + allowed_distance
        if direction is TradeDirection.LONG
        else preferred - allowed_distance
    )
    lower = explicit_lower if explicit_lower is not None else preferred - half_width
    upper = explicit_upper if explicit_upper is not None else preferred + half_width
    configured_max_chase = (
        explicit_max_chase if explicit_max_chase is not None else derived_max_chase
    )
    # Strategy references are internal hints, not user-authored order instructions.
    # A hint inside the zone used to abort the complete symbol analysis.  Clamp it
    # to the trade-side zone edge instead: this is the narrowest valid chase
    # boundary and therefore does not authorize any additional price chasing.
    max_chase_price = (
        max(configured_max_chase, upper)
        if direction is TradeDirection.LONG
        else min(configured_max_chase, lower)
    )
    location_quality = 1.0 if allowed_distance == 0 else max(0.0, 1.0 - distance / allowed_distance)
    return EntryZone(
        lower=lower,
        upper=upper,
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
        expires_after_seconds=(
            explicit_expiry_seconds
            if explicit_expiry_seconds is not None
            else config.default_expiry_seconds
        ),
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


def _maximum_chase_is_directionally_valid(*, zone: EntryZone, direction: TradeDirection) -> bool:
    if zone.max_chase_price is None:
        return True
    if direction is TradeDirection.LONG:
        return zone.max_chase_price >= zone.upper
    return zone.max_chase_price <= zone.lower


def _validate_execution_tolerance_inputs(
    *, tick_size: float | None, spread_percentage: float | None
) -> None:
    if tick_size is not None and (not math.isfinite(tick_size) or tick_size <= 0.0):
        raise ValueError("tick size must be positive and finite when provided")
    if spread_percentage is not None and (
        not math.isfinite(spread_percentage) or spread_percentage < 0.0
    ):
        raise ValueError("spread percentage must be finite and non-negative when provided")


def _risk_reward(*, price: float, invalidation_price: float, target_price: float) -> float:
    risk = abs(price - invalidation_price)
    reward = abs(target_price - price)
    return reward / risk if risk > 0 else 0.0
