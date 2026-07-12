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
from apex.structure.contracts import ConfirmationStatus, StructureAnalysisResult


@dataclass(frozen=True, slots=True)
class LiquidityEvidenceSummary:
    """Compact explainable snapshot of liquidity state and event evidence."""

    zone_count: int
    active_zone_count: int
    swept_zone_count: int
    consumed_zone_count: int
    sweep_count: int
    confirmed_sweep_count: int
    unresolved_breach_count: int
    trap_count: int
    confirmed_trap_count: int
    strongest_zone_price: float | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "zone_count",
            "active_zone_count",
            "swept_zone_count",
            "consumed_zone_count",
            "sweep_count",
            "confirmed_sweep_count",
            "unresolved_breach_count",
            "trap_count",
            "confirmed_trap_count",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
        counted_zones = self.active_zone_count + self.swept_zone_count + self.consumed_zone_count
        if counted_zones > self.zone_count:
            raise ValueError("liquidity-zone status counts cannot exceed total zones")
        if self.confirmed_sweep_count > self.sweep_count:
            raise ValueError("confirmed sweep count cannot exceed total sweeps")
        if self.unresolved_breach_count > self.sweep_count:
            raise ValueError("unresolved breach count cannot exceed total sweeps")
        if self.confirmed_trap_count > self.trap_count:
            raise ValueError("confirmed trap count cannot exceed total traps")
        if self.strongest_zone_price is not None and self.strongest_zone_price <= 0:
            raise ValueError("strongest zone price must be positive when provided")


@dataclass(frozen=True, slots=True)
class LiquidityAnalysisResult:
    zones: tuple[LiquidityZone, ...]
    sweeps: tuple[LiquiditySweep, ...]
    traps: tuple[TrapEvent, ...]
    evidence_summary: LiquidityEvidenceSummary | None = None

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
        if self.evidence_summary is None:
            object.__setattr__(self, "evidence_summary", _summarize_liquidity(self))


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


def _summarize_liquidity(result: LiquidityAnalysisResult) -> LiquidityEvidenceSummary:
    strongest = max(
        result.zones,
        key=lambda item: (item.strength, item.touch_count, -item.age, item.representative_price),
        default=None,
    )
    confirmed_sweeps = tuple(
        item
        for item in result.sweeps
        if item.classification is SweepClassification.CONFIRMED_SWEEP
        and item.confirmation is ConfirmationStatus.CONFIRMED
    )
    unresolved = tuple(
        item
        for item in result.sweeps
        if item.classification is SweepClassification.UNRESOLVED_BREACH
    )
    confirmed_traps = tuple(
        item for item in result.traps if item.confirmation is ConfirmationStatus.CONFIRMED
    )
    notes: list[str] = []
    if strongest is not None:
        notes.append(
            "strongest_zone="
            f"{strongest.side.value}:{strongest.kind.value};"
            f"price={strongest.representative_price:.8g};"
            f"strength={strongest.strength:.3f}"
        )
    if confirmed_sweeps:
        notes.append("confirmed_sweep_present")
    if confirmed_traps:
        notes.append("confirmed_trap_present")
    return LiquidityEvidenceSummary(
        zone_count=len(result.zones),
        active_zone_count=sum(
            1 for item in result.zones if item.status is LiquidityZoneStatus.ACTIVE
        ),
        swept_zone_count=sum(
            1 for item in result.zones if item.status is LiquidityZoneStatus.SWEPT
        ),
        consumed_zone_count=sum(
            1 for item in result.zones if item.status is LiquidityZoneStatus.CONSUMED
        ),
        sweep_count=len(result.sweeps),
        confirmed_sweep_count=len(confirmed_sweeps),
        unresolved_breach_count=len(unresolved),
        trap_count=len(result.traps),
        confirmed_trap_count=len(confirmed_traps),
        strongest_zone_price=strongest.representative_price if strongest is not None else None,
        notes=tuple(notes),
    )
