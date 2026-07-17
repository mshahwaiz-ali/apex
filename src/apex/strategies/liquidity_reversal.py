"""Deterministic liquidity-reversal candidate generation."""

from __future__ import annotations

from datetime import datetime

from apex.liquidity.contracts import (
    LiquiditySide,
    LiquiditySweep,
    SweepClassification,
    TrapEvent,
    TrapType,
)
from apex.strategies.context import StrategyContext
from apex.strategies.contracts import (
    EntryMode,
    InvalidationConcept,
    InvalidationType,
    RawQualityMetrics,
    StrategyEvidence,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)
from apex.strategies.strategy_types import StrategyType
from apex.strategies.entry import (
    DEFAULT_ENTRY_SELECTION_CONFIG,
    EntryReference,
    EntrySelectionConfig,
    select_entry_zone,
)
from apex.structure.contracts import ConfirmationStatus, LevelRole, LevelStatus


def generate_liquidity_reversal_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
    entry_config: EntrySelectionConfig = DEFAULT_ENTRY_SELECTION_CONFIG,
    minimum_close_recovery: float = 0.25,
) -> tuple[TradeCandidate, ...]:
    """Generate confirmed sweep-and-trap reversals in stable direction order."""

    candidates = tuple(
        candidate
        for direction in (TradeDirection.LONG, TradeDirection.SHORT)
        if (
            candidate := _candidate_for_direction(
                context,
                direction=direction,
                decision_time=decision_time,
                entry_config=entry_config,
                minimum_close_recovery=minimum_close_recovery,
            )
        )
        is not None
    )
    return tuple(sorted(candidates, key=lambda item: item.direction.value))


def _candidate_for_direction(
    context: StrategyContext,
    *,
    direction: TradeDirection,
    decision_time: datetime,
    entry_config: EntrySelectionConfig,
    minimum_close_recovery: float,
) -> TradeCandidate | None:
    bullish = direction is TradeDirection.LONG
    frame = context.decision_frame
    sweep = _latest_confirmed_sweep(frame.liquidity.sweeps, bullish=bullish)
    if sweep is None or sweep.close_recovery < minimum_close_recovery:
        return None

    trap = _matching_confirmed_trap(frame.liquidity.traps, sweep=sweep, bullish=bullish)
    if trap is None:
        return None
    if not _momentum_allows_reversal(context, bullish=bullish):
        return None

    current = context.current_price
    atr = context.atr
    invalidation_price = sweep.zone.low - atr * 0.15 if bullish else sweep.zone.high + atr * 0.15
    target_price = _target_price(context, bullish=bullish)
    if not _valid_geometry(
        current=current,
        invalidation=invalidation_price,
        target=target_price,
        bullish=bullish,
    ):
        return None

    recovery_reference = sweep.zone.high if bullish else sweep.zone.low
    entry = select_entry_zone(
        current_price=current,
        atr=atr,
        direction=direction,
        invalidation_price=invalidation_price,
        target_price=target_price,
        references=(
            EntryReference(
                price=recovery_reference,
                mode=EntryMode.SWEEP_RECOVERY,
                rationale=("recovered liquidity boundary offers a defined reversal entry",),
                scaled=sweep.zone.low < sweep.zone.high,
            ),
        ),
        config=entry_config,
    )
    warnings = ("active-candle evidence is provisional",) if context.provisional else ()
    momentum_quality = _momentum_quality(context, bullish=bullish)
    liquidity_quality = min(
        1.0,
        sweep.zone.strength * 0.5
        + min(1.0, sweep.close_recovery) * 0.3
        + min(1.0, sweep.penetration) * 0.2,
    )
    return TradeCandidate(
        symbol=context.symbol,
        strategy=StrategyType.LIQUIDITY_REJECTION_REVERSAL,
        direction=direction,
        decision_time=decision_time,
        entry=entry,
        invalidation=InvalidationConcept(
            kind=InvalidationType.LIQUIDITY,
            price=invalidation_price,
            rationale=(
                "reversal thesis fails beyond the swept sell-side liquidity"
                if bullish
                else "reversal thesis fails beyond the swept buy-side liquidity",
            ),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=target_price,
                    label="primary",
                    rationale=("nearest opposing structure or range objective",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=_trend_alignment(context, bullish=bullish),
            structure_quality=0.7,
            entry_quality=entry.location_quality,
            momentum_quality=momentum_quality,
            volume_quality=_volume_quality(context),
            liquidity_quality=liquidity_quality,
            target_space_quality=_target_space_quality(
                current=current,
                invalidation=invalidation_price,
                target=target_price,
            ),
            extension_penalty=1.0 - entry.location_quality,
            conflict_penalty=0.0,
        ),
        evidence=StrategyEvidence(
            supporting=(
                f"confirmed {sweep.zone.side.value} liquidity sweep",
                f"confirmed {trap.kind.value} rejection",
                "price recovered through the swept liquidity boundary",
                "entry remains inside the volatility-aware near-CMP limit",
            ),
            warnings=warnings,
            feature_references=tuple(
                name
                for name, value in (
                    ("rsi", frame.features.rsi),
                    ("rsi_slope", frame.features.rsi_slope),
                    ("macd_histogram", frame.features.macd_histogram),
                    ("rate_of_change", frame.features.rate_of_change),
                    ("relative_volume", frame.features.relative_volume),
                )
                if value is not None
            ),
            structure_references=("levels", "ranges"),
            liquidity_references=("zones", "sweeps", "traps"),
        ),
        metadata={
            "sweep_candle_index": sweep.candle_index,
            "trap_type": trap.kind.value,
            "close_recovery": sweep.close_recovery,
        },
        provisional=context.provisional,
    )


def _latest_confirmed_sweep(
    sweeps: tuple[LiquiditySweep, ...],
    *,
    bullish: bool,
) -> LiquiditySweep | None:
    side = LiquiditySide.SELL_SIDE if bullish else LiquiditySide.BUY_SIDE
    eligible = tuple(
        sweep
        for sweep in sweeps
        if sweep.zone.side is side
        and sweep.classification is SweepClassification.CONFIRMED_SWEEP
        and sweep.confirmation is ConfirmationStatus.CONFIRMED
    )
    return max(eligible, key=lambda item: item.candle_index, default=None)


def _matching_confirmed_trap(
    traps: tuple[TrapEvent, ...],
    *,
    sweep: LiquiditySweep,
    bullish: bool,
) -> TrapEvent | None:
    expected = TrapType.BEAR_TRAP if bullish else TrapType.BULL_TRAP
    eligible = tuple(
        trap
        for trap in traps
        if trap.sweep == sweep
        and trap.kind is expected
        and trap.confirmation is ConfirmationStatus.CONFIRMED
    )
    return max(eligible, key=lambda item: item.candle_index, default=None)


def _momentum_allows_reversal(context: StrategyContext, *, bullish: bool) -> bool:
    features = context.decision_frame.features
    if features.rsi is not None:
        if bullish and features.rsi > 65:
            return False
        if not bullish and features.rsi < 35:
            return False
    directional = tuple(
        value
        for value in (features.rsi_slope, features.macd_histogram, features.rate_of_change)
        if value is not None
    )
    if not directional:
        return True
    return (
        any(value >= 0 for value in directional)
        if bullish
        else any(value <= 0 for value in directional)
    )


def _momentum_quality(context: StrategyContext, *, bullish: bool) -> float:
    features = context.decision_frame.features
    signals = tuple(
        value
        for value in (features.rsi_slope, features.macd_histogram, features.rate_of_change)
        if value is not None
    )
    if not signals:
        return 0.5
    aligned = sum(value >= 0 if bullish else value <= 0 for value in signals)
    return aligned / len(signals)


def _trend_alignment(context: StrategyContext, *, bullish: bool) -> float:
    direction = context.decision_frame.structure.trend.direction.value
    if bullish and "bullish" in direction:
        return 0.8
    if not bullish and "bearish" in direction:
        return 0.8
    if direction in {"range", "transition", "uncertain"}:
        return 0.6
    return 0.3


def _volume_quality(context: StrategyContext) -> float:
    value = context.decision_frame.features.relative_volume
    return 0.5 if value is None else min(1.0, value / 2.0)


def _target_price(context: StrategyContext, *, bullish: bool) -> float:
    frame = context.decision_frame
    current = context.current_price
    role = LevelRole.RESISTANCE if bullish else LevelRole.SUPPORT
    levels = [
        level.representative_price
        for level in frame.structure.levels
        if level.role is role
        and level.status is not LevelStatus.BROKEN
        and (
            (bullish and level.representative_price > current)
            or (not bullish and level.representative_price < current)
        )
    ]
    if levels:
        return min(levels) if bullish else max(levels)
    ranges = [
        detected.high if bullish else detected.low
        for detected in frame.structure.ranges
        if (bullish and detected.high > current) or (not bullish and detected.low < current)
    ]
    if ranges:
        return min(ranges) if bullish else max(ranges)
    return current + context.atr * 2.2 if bullish else current - context.atr * 2.2


def _target_space_quality(*, current: float, invalidation: float, target: float) -> float:
    risk = abs(current - invalidation)
    reward = abs(target - current)
    if risk <= 0:
        return 0.0
    return min(1.0, reward / risk / 3.0)


def _valid_geometry(*, current: float, invalidation: float, target: float, bullish: bool) -> bool:
    return invalidation < current < target if bullish else target < current < invalidation
