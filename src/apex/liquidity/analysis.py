"""High-level deterministic liquidity orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from apex.domain.models import Candle
from apex.features.validation import ActiveCandlePolicy, prepare_candles
from apex.liquidity.contracts import LiquiditySweep, LiquidityZone, TrapEvent
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
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
    zone_tolerance: float = 0.002,
) -> LiquidityAnalysisResult:
    """Run zones, sweeps, and traps in a fixed explainable order."""

    usable = prepare_candles(
        candles,
        minimum_candles=1,
        active_candle_policy=active_candle_policy,
    )
    zones = derive_liquidity_zones(
        structure.swings,
        current_index=len(usable) - 1,
        tolerance=zone_tolerance,
        ranges=structure.ranges,
    )
    sweeps = detect_liquidity_sweeps(
        candles,
        zones,
        active_candle_policy=active_candle_policy,
    )
    traps = detect_traps(usable, sweeps)
    return LiquidityAnalysisResult(
        zones=zones,
        sweeps=tuple(
            sorted(sweeps, key=lambda item: (item.candle_index, item.zone.side.value))
        ),
        traps=tuple(sorted(traps, key=lambda item: (item.candle_index, item.kind.value))),
    )
