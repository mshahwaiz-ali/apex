"""High-level deterministic liquidity orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from apex.domain.models import Candle
from apex.features.validation import ActiveCandlePolicy
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
        if tuple(sorted(self.zones, key=lambda item: (item.representative_price, item.side.value))) != self.zones:
            raise ValueError("liquidity zones must use deterministic ordering")
        if tuple(sorted(self.sweeps, key=lambda item: item.candle_index)) != self.sweeps:
            raise ValueError("liquidity sweeps must use chronological ordering")
        if tuple(sorted(self.traps, key=lambda item: item.candle_index)) != self.traps:
            raise ValueError("trap events must use chronological ordering")


def analyze_liquidity(
    candles: Sequence[Candle],
    structure: StructureAnalysisResult,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> LiquidityAnalysisResult:
    """Run zones, sweeps, and traps in a fixed explainable order."""

    zones = derive_liquidity_zones(structure.swings, structure.ranges, candles)
    sweeps = detect_liquidity_sweeps(
        candles,
        zones,
        active_candle_policy=active_candle_policy,
    )
    traps = detect_traps(candles, sweeps)
    return LiquidityAnalysisResult(
        zones=tuple(sorted(zones, key=lambda item: (item.representative_price, item.side.value))),
        sweeps=tuple(sorted(sweeps, key=lambda item: item.candle_index)),
        traps=tuple(sorted(traps, key=lambda item: item.candle_index)),
    )
