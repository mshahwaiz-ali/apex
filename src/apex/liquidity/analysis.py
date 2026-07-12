"""High-level deterministic liquidity orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from apex.domain.models import Candle
from apex.features.validation import ActiveCandlePolicy, prepare_candles
from apex.liquidity.contracts import (
    LiquiditySweep,
    LiquidityZone,
    LiquidityZoneStatus,
    SweepClassification,
    TrapEvent,
)
from apex.liquidity.sweeps import detect_liquidity_sweeps
from apex.liquidity.traps import detect_traps
from apex.liquidity.zones import derive_liquidity_zones
from apex.structure.contracts import StructureAnalysisResult


@dataclass(frozen=True, slots=True)
class LiquidityAnalysisResult:
    zones: tuple[LiquidityZone, ...]
    sweeps: tuple[LiquiditySweep, ...]
    traps: tuple[TrapEvent, ...]

    def __post_init__(self) -> None:
        expected_zones = tuple(
            sorted(
                self.zones,
                key=lambda item: (
                    item.representative_price,
                    item.side.value,
                    item.kind.value,
                    item.created_index,
                ),
            )
        )
        if expected_zones != self.zones:
            raise ValueError("liquidity zones must use deterministic ordering")
        expected_sweeps = tuple(
            sorted(self.sweeps, key=lambda item: (item.candle_index, item.zone.side.value))
        )
        if expected_sweeps != self.sweeps:
            raise ValueError("liquidity sweeps must use chronological ordering")
        expected_traps = tuple(
            sorted(self.traps, key=lambda item: (item.candle_index, item.kind.value))
        )
        if expected_traps != self.traps:
            raise ValueError("trap events must use chronological ordering")


def analyze_liquidity(
    candles: Sequence[Candle],
    structure: StructureAnalysisResult,
    *,
    relative_volume: Sequence[float | None] | None = None,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
    zone_tolerance: float = 0.002,
) -> LiquidityAnalysisResult:
    """Run zones, sweeps, and traps in a fixed explainable order."""

    if relative_volume is not None and len(relative_volume) != len(candles):
        raise ValueError("relative_volume length must match candle count")
    usable = prepare_candles(
        candles,
        minimum_candles=1,
        active_candle_policy=active_candle_policy,
    )
    usable_volume = tuple(relative_volume[: len(usable)]) if relative_volume is not None else None
    zones = derive_liquidity_zones(
        structure.swings,
        current_index=len(usable) - 1,
        tolerance=zone_tolerance,
        ranges=structure.ranges,
    )
    detected_sweeps = detect_liquidity_sweeps(
        usable,
        zones,
        relative_volume=usable_volume,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    )
    zones, sweeps = _synchronize_zone_status(zones, detected_sweeps)
    traps = detect_traps(usable, sweeps)
    return LiquidityAnalysisResult(
        zones=zones,
        sweeps=tuple(sorted(sweeps, key=lambda item: (item.candle_index, item.zone.side.value))),
        traps=tuple(sorted(traps, key=lambda item: (item.candle_index, item.kind.value))),
    )


def _synchronize_zone_status(
    zones: Sequence[LiquidityZone],
    sweeps: Sequence[LiquiditySweep],
) -> tuple[tuple[LiquidityZone, ...], tuple[LiquiditySweep, ...]]:
    status_by_zone = {
        sweep.zone: _status_for_classification(sweep.classification) for sweep in sweeps
    }
    replacements = {
        zone: replace(zone, status=status_by_zone.get(zone, zone.status)) for zone in zones
    }
    updated_zones = tuple(
        sorted(
            replacements.values(),
            key=lambda item: (
                item.representative_price,
                item.side.value,
                item.kind.value,
                item.created_index,
            ),
        )
    )
    updated_sweeps = tuple(replace(sweep, zone=replacements[sweep.zone]) for sweep in sweeps)
    return updated_zones, updated_sweeps


def _status_for_classification(
    classification: SweepClassification,
) -> LiquidityZoneStatus:
    if classification is SweepClassification.CONFIRMED_SWEEP:
        return LiquidityZoneStatus.SWEPT
    if classification is SweepClassification.SIMPLE_BREAKOUT:
        return LiquidityZoneStatus.CONSUMED
    return LiquidityZoneStatus.BREACHED
