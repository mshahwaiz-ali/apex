"""Deterministic multi-timeframe structural target ladder construction."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from apex.strategies.context import StrategyContext, TimeframeContext
from apex.strategies.contracts import (
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)
from apex.structure.contracts import LevelRole, LevelStatus, StructureLevel

_MAX_STRUCTURAL_TARGETS = 3
_FRONT_RUN_ZONE_FRACTION = 0.25
_FRONT_RUN_ATR_MIN_FRACTION = 0.05
_FRONT_RUN_ATR_MAX_FRACTION = 0.15
_DEFAULT_MAX_DISTANCE_ATR = 12.0


@dataclass(frozen=True, slots=True)
class StructuralTargetCandidate:
    """One opposing structural zone projected into an executable target price."""

    price: float
    zone_low: float
    zone_high: float
    timeframe: str
    role: LevelRole
    touches: int
    distance: float
    front_run_buffer: float


def build_structural_target_ladder(
    context: StrategyContext,
    *,
    direction: TradeDirection,
    max_targets: int = _MAX_STRUCTURAL_TARGETS,
    max_distance_atr: float = _DEFAULT_MAX_DISTANCE_ATR,
    max_timeframe_minutes: int | None = None,
) -> tuple[TargetLevel, ...]:
    """Return nearest-first targets across relevant configured timeframes."""

    if max_targets < 1:
        raise ValueError("max targets must be at least one")
    if max_distance_atr <= 0.0:
        raise ValueError("max distance ATR must be positive")

    candidates = _collect_candidates(
        context,
        direction=direction,
        max_distance_atr=max_distance_atr,
        max_timeframe_minutes=max_timeframe_minutes,
    )
    selected: list[StructuralTargetCandidate] = []
    for candidate in candidates:
        if any(_zones_overlap(candidate, existing) for existing in selected):
            continue
        selected.append(candidate)
        if len(selected) >= max_targets:
            break

    return tuple(
        TargetLevel(
            kind=TargetType.STRUCTURAL,
            price=candidate.price,
            label=f"tp{index}",
            rationale=(
                f"front-run of {candidate.timeframe} opposing {candidate.role.value} zone "
                f"{candidate.zone_low:g}-{candidate.zone_high:g}",
                f"zone has {candidate.touches} confirmed structural touch(es)",
            ),
        )
        for index, candidate in enumerate(selected, start=1)
    )


def apply_target_ladder_to_candidates(
    context: StrategyContext,
    candidates: tuple[TradeCandidate, ...],
    *,
    max_targets: int = _MAX_STRUCTURAL_TARGETS,
) -> tuple[TradeCandidate, ...]:
    """Apply horizon-aware nearest-obstacle target ordering to every strategy."""

    if max_targets < 1:
        raise ValueError("max targets must be at least one")
    return tuple(
        _apply_target_ladder(context, candidate, max_targets=max_targets)
        for candidate in candidates
    )


def _apply_target_ladder(
    context: StrategyContext,
    candidate: TradeCandidate,
    *,
    max_targets: int,
) -> TradeCandidate:
    max_distance_atr, max_timeframe_minutes = _target_scope(candidate)
    structural = build_structural_target_ladder(
        context,
        direction=candidate.direction,
        max_targets=max_targets,
        max_distance_atr=max_distance_atr,
        max_timeframe_minutes=max_timeframe_minutes,
    )
    originals = tuple(
        level
        for level in candidate.targets.levels
        if _target_is_valid_for_candidate(candidate, level)
    )
    combined = (*structural, *originals)
    ordered = sorted(
        (
            level
            for level in combined
            if _target_is_valid_for_candidate(candidate, level)
        ),
        key=lambda level: (
            abs(level.price - context.current_price),
            1 if level.kind is TargetType.EXPANSION else 0,
            level.price,
        ),
    )
    tolerance = max(
        context.atr * _FRONT_RUN_ATR_MAX_FRACTION,
        context.current_price * 1e-6,
    )
    unique: list[TargetLevel] = []
    for level in ordered:
        if any(abs(level.price - existing.price) <= tolerance for existing in unique):
            continue
        unique.append(level)

    selected = _select_ladder_levels(
        unique,
        originals=originals,
        current=context.current_price,
        max_targets=max_targets,
    )
    if not selected:
        selected = list(originals[:max_targets])
    if not selected:
        fallback = fallback_expansion_target(context, direction=candidate.direction)
        if _target_is_valid_for_candidate(candidate, fallback):
            selected = [fallback]
        else:
            return candidate

    relabelled = tuple(
        replace(level, label=f"tp{index}") for index, level in enumerate(selected, start=1)
    )
    metadata = dict(candidate.metadata)
    metadata.update(target_ladder_metadata(relabelled))
    metadata["target_ladder_scope"] = "all_strategy_families"
    metadata["target_ladder_first_obstacle_authoritative"] = bool(structural)
    metadata["target_ladder_max_distance_atr"] = max_distance_atr
    metadata["target_ladder_max_timeframe_minutes"] = (
        max_timeframe_minutes if max_timeframe_minutes is not None else 0
    )
    metadata["target_ladder_runner_preserved"] = _runner_was_preserved(
        relabelled,
        originals=originals,
        current=context.current_price,
        tolerance=tolerance,
    )
    metadata["target_1_management"] = "reduce at first obstacle or earlier confirmed rejection"
    if len(relabelled) >= 2:
        metadata["target_2_activation"] = "continue only after TP1 zone breaks and holds"
    if len(relabelled) >= 3:
        metadata["target_3_activation"] = "runner only while continuation structure remains valid"
    return replace(
        candidate,
        targets=TargetConcept(levels=relabelled),
        metadata=metadata,
    )


def _target_scope(candidate: TradeCandidate) -> tuple[float, int | None]:
    relationship = _enum_value(candidate.layered_state.timeframe_relationship)
    horizon = _enum_value(candidate.layered_state.holding_horizon)

    if relationship == "countertrend_scalp" or horizon == "scalp":
        return 4.0, 15
    if horizon in {"intraday", "session"}:
        return 8.0, 60
    if horizon == "multi_hour":
        return 16.0, 240
    if horizon == "swing":
        return 40.0, 1440
    if horizon == "runner":
        return 80.0, None
    return _DEFAULT_MAX_DISTANCE_ATR, 240


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return "" if raw is None else str(raw).strip().lower()


def _select_ladder_levels(
    ordered: list[TargetLevel],
    *,
    originals: tuple[TargetLevel, ...],
    current: float,
    max_targets: int,
) -> list[TargetLevel]:
    if len(ordered) <= max_targets:
        return ordered
    if max_targets == 1:
        return ordered[:1]

    farthest_original = max(
        originals,
        key=lambda level: abs(level.price - current),
        default=None,
    )
    if farthest_original is None:
        return ordered[:max_targets]

    selected = ordered[: max_targets - 1]
    if farthest_original not in selected:
        selected.append(farthest_original)
    selected.sort(key=lambda level: abs(level.price - current))
    return selected[:max_targets]


def _runner_was_preserved(
    levels: tuple[TargetLevel, ...],
    *,
    originals: tuple[TargetLevel, ...],
    current: float,
    tolerance: float,
) -> bool:
    if not originals or len(levels) < 2:
        return False
    farthest_original = max(
        originals,
        key=lambda level: abs(level.price - current),
    )
    return any(abs(level.price - farthest_original.price) <= tolerance for level in levels[1:])


def _target_is_valid_for_candidate(
    candidate: TradeCandidate,
    level: TargetLevel,
) -> bool:
    opportunities = candidate.entry_opportunities or (candidate.entry,)
    if candidate.direction is TradeDirection.LONG:
        required_boundary = max(opportunity.upper for opportunity in opportunities)
        return level.price > required_boundary
    required_boundary = min(opportunity.lower for opportunity in opportunities)
    return level.price < required_boundary


def fallback_expansion_target(
    context: StrategyContext,
    *,
    direction: TradeDirection,
) -> TargetLevel:
    """Return one decision-frame ATR objective when no verified obstacle exists."""

    bullish = direction is TradeDirection.LONG
    price = (
        context.current_price + context.atr * 2.4
        if bullish
        else context.current_price - context.atr * 2.4
    )
    return TargetLevel(
        kind=TargetType.EXPANSION,
        price=price,
        label="tp1",
        rationale=(
            f"2.4 ATR expansion projection on {context.decision_frame.timeframe}; "
            "no verified opposing structure was available",
        ),
    )


def target_ladder_metadata(levels: tuple[TargetLevel, ...]) -> dict[str, str | int | float | bool]:
    """Return compact scalar provenance suitable for candidate metadata."""

    metadata: dict[str, str | int | float | bool] = {
        "target_ladder_enabled": True,
        "target_ladder_count": len(levels),
    }
    for index, level in enumerate(levels, start=1):
        metadata[f"target_{index}_price"] = level.price
        metadata[f"target_{index}_type"] = level.kind.value
        metadata[f"target_{index}_basis"] = level.rationale[0]
        timeframe = _timeframe_from_rationale(level.rationale)
        if timeframe is not None:
            metadata[f"target_{index}_timeframe"] = timeframe
    return metadata


def _timeframe_from_rationale(rationale: tuple[str, ...]) -> str | None:
    for item in rationale:
        words = item.replace(";", " ").replace(",", " ").split()
        for word in words:
            value = word.strip().lower()
            if value.endswith(("m", "h", "d")) and value[:-1].isdigit():
                return value
    return None


def _collect_candidates(
    context: StrategyContext,
    *,
    direction: TradeDirection,
    max_distance_atr: float,
    max_timeframe_minutes: int | None,
) -> tuple[StructuralTargetCandidate, ...]:
    bullish = direction is TradeDirection.LONG
    role = LevelRole.RESISTANCE if bullish else LevelRole.SUPPORT
    candidates: list[StructuralTargetCandidate] = []

    for frame in context.frames:
        timeframe_minutes = _timeframe_minutes(frame.timeframe)
        if (
            max_timeframe_minutes is not None
            and timeframe_minutes is not None
            and timeframe_minutes > max_timeframe_minutes
        ):
            continue
        for level in frame.structure.levels:
            candidate = _candidate_from_level(
                frame,
                level,
                current=context.current_price,
                bullish=bullish,
                expected_role=role,
            )
            if candidate is None:
                continue
            if candidate.distance > context.atr * max_distance_atr:
                continue
            candidates.append(candidate)

    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.distance,
                -item.touches,
                item.zone_high - item.zone_low,
                item.timeframe,
            ),
        )
    )


def _candidate_from_level(
    frame: TimeframeContext,
    level: StructureLevel,
    *,
    current: float,
    bullish: bool,
    expected_role: LevelRole,
) -> StructuralTargetCandidate | None:
    if level.role is not expected_role or level.status is LevelStatus.BROKEN:
        return None
    if bullish and level.high <= current:
        return None
    if not bullish and level.low >= current:
        return None

    zone_width = max(level.high - level.low, 0.0)
    atr = frame.features.atr
    minimum_buffer = max(current * 1e-6, atr * _FRONT_RUN_ATR_MIN_FRACTION)
    desired_buffer = max(zone_width * _FRONT_RUN_ZONE_FRACTION, minimum_buffer)
    buffer = min(desired_buffer, atr * _FRONT_RUN_ATR_MAX_FRACTION)
    raw_price = level.low - buffer if bullish else level.high + buffer
    price = _quantize_toward_current(
        raw_price,
        current=current,
        tick_size=frame.exchange_tick_size,
        atr=atr,
        bullish=bullish,
    )
    if bullish and price <= current:
        return None
    if not bullish and price >= current:
        return None

    return StructuralTargetCandidate(
        price=price,
        zone_low=level.low,
        zone_high=level.high,
        timeframe=frame.timeframe,
        role=level.role,
        touches=level.touches,
        distance=abs(price - current),
        front_run_buffer=abs((level.low if bullish else level.high) - price),
    )


def _quantize_toward_current(
    price: float,
    *,
    current: float,
    tick_size: float | None,
    atr: float,
    bullish: bool,
) -> float:
    if tick_size is None or tick_size <= 0.0:
        return price
    plausible_tick = min(atr * 0.25, current * 0.01)
    if tick_size > plausible_tick:
        return price
    units = price / tick_size
    return (
        math.floor(units + 1e-12) * tick_size
        if bullish
        else math.ceil(units - 1e-12) * tick_size
    )


def _timeframe_minutes(timeframe: str) -> int | None:
    value = timeframe.strip().lower()
    if len(value) < 2 or not value[:-1].isdigit():
        return None
    amount = int(value[:-1])
    unit = value[-1]
    return {
        "m": amount,
        "h": amount * 60,
        "d": amount * 1440,
    }.get(unit)


def _zones_overlap(
    first: StructuralTargetCandidate,
    second: StructuralTargetCandidate,
) -> bool:
    return max(first.zone_low, second.zone_low) <= min(first.zone_high, second.zone_high)


__all__ = [
    "StructuralTargetCandidate",
    "apply_target_ladder_to_candidates",
    "build_structural_target_ladder",
    "fallback_expansion_target",
    "target_ladder_metadata",
]
