"""Deterministic multi-timeframe structural target ladder construction."""

from __future__ import annotations

from dataclasses import dataclass

from apex.strategies.context import StrategyContext, TimeframeContext
from apex.strategies.contracts import TargetLevel, TargetType, TradeDirection
from apex.structure.contracts import LevelRole, LevelStatus, StructureLevel

_MAX_STRUCTURAL_TARGETS = 3
_FRONT_RUN_ZONE_FRACTION = 0.25
_FRONT_RUN_ATR_FRACTION = 0.15


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
) -> tuple[TargetLevel, ...]:
    """Return nearest-first targets across all relevant configured timeframes.

    Targets are placed just before the opposing zone using a volatility- and
    zone-width-aware buffer. Overlapping zones are deduplicated so a distant
    higher-timeframe objective cannot silently replace a nearer obstacle.
    """

    if max_targets < 1:
        raise ValueError("max targets must be at least one")

    candidates = _collect_candidates(context, direction=direction)
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
    return metadata


def _collect_candidates(
    context: StrategyContext,
    *,
    direction: TradeDirection,
) -> tuple[StructuralTargetCandidate, ...]:
    bullish = direction is TradeDirection.LONG
    role = LevelRole.RESISTANCE if bullish else LevelRole.SUPPORT
    candidates: list[StructuralTargetCandidate] = []

    for frame in context.frames:
        for level in frame.structure.levels:
            candidate = _candidate_from_level(
                frame,
                level,
                current=context.current_price,
                bullish=bullish,
                expected_role=role,
            )
            if candidate is not None:
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
    tick_size = frame.exchange_tick_size or 0.0
    buffer = max(
        tick_size,
        min(zone_width * _FRONT_RUN_ZONE_FRACTION, frame.features.atr * _FRONT_RUN_ATR_FRACTION),
    )
    raw_price = level.low - buffer if bullish else level.high + buffer
    if bullish and raw_price <= current:
        return None
    if not bullish and raw_price >= current:
        return None

    return StructuralTargetCandidate(
        price=raw_price,
        zone_low=level.low,
        zone_high=level.high,
        timeframe=frame.timeframe,
        role=level.role,
        touches=level.touches,
        distance=abs(raw_price - current),
        front_run_buffer=buffer,
    )


def _zones_overlap(
    first: StructuralTargetCandidate,
    second: StructuralTargetCandidate,
) -> bool:
    return max(first.zone_low, second.zone_low) <= min(first.zone_high, second.zone_high)


__all__ = [
    "StructuralTargetCandidate",
    "build_structural_target_ladder",
    "fallback_expansion_target",
    "target_ladder_metadata",
]
