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
    traps: tuple[