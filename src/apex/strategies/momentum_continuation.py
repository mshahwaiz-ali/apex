"""Deterministic momentum-continuation candidate generation."""

from __future__ import annotations

from datetime import datetime

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import (
    EntryMode,
    InvalidationConcept,
    InvalidationType,
    RawQualityMetrics,
    StrategyEvidence,
    StrategyType,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)
from apex.strategies.entry import EntryReference, EntrySelectionConfig, select_entry_zone
from apex.structure.contracts import BreakDirection, BreakQuality, ConfirmationStatus, LevelRole, LevelStatus, TrendDirection

_BULLISH_TRENDS = {
    TrendDirection.STRONG_BULLISH,
    TrendDirection.BULLISH,
    TrendDirection.WEAK_BULLISH,
}
_BEARISH_TRENDS = {
    TrendDirection.STRONG_BEARISH,
    TrendDirection.BEARISH,
    TrendDirection.WEAK_BEARISH,
}


def generate_momentum_continuation_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
    entry_config: EntrySelectionConfig = EntrySelectionConfig(),
) -> tuple[TradeCandidate, ...]:
    """Generate near-CMP momentum continuations in stable direction order."""

    candidates = tuple(
        candidate
        for direction in (TradeDirection.LONG, TradeDirection.SHORT)
        if (
            candidate := _candidate_for_direction(
                context,
                direction=direction,
                decision_time=decision_time,
                entry_config=entry_config,
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
) -> TradeCandidate | None:
    bullish = direction is TradeDirection.LONG
    frame = context.decision_frame
    accepted = _BULLISH_TRENDS if bullish else _BEARISH_TRENDS
    has_trend = frame.structure.trend.direction in accepted
    has_break = _has_recent_continuation_break(context, bullish=bullish)
    if not has_trend and not has_break:
        return None
    if context.higher_timeframe_contradiction(bullish=bullish):
        return None

    aligned, total = _momentum_alignment(context, bullish=bullish)
    if total == 0 or aligned == 0:
        return None
    if aligned * 2 < total:
        return None

    current = context.current_price
    atr = context.atr
    invalidation_price = _invalidation_price(context, bullish=bullish)
    target_price = _target_price(context, bullish=bullish)
    if not _valid_geometry(
        current=current,
        invalidation=invalidation_price,
        target=target_price,
        bullish=bullish,
    ):
        return None

    references = _entry_references(context, bullish=bullish)
    entry = select_entry_zone(
        current_price=current,
        atr=atr,
        direction=direction,
        invalidation_price=invalidation_price,
        target_price=target_price,
        references=references,
        config=entry_config,
    )
    if entry.is_extended:
        return None

    features = frame.features
    warnings = ("active-candle evidence is provisional",) if context.provisional else ()
    return TradeCandidate(
        symbol=context.symbol,
        strategy=StrategyType.MOMENTUM_CONTINUATION,
        direction=direction,
        decision_time=decision_time,
        entry=entry,
        invalidation=InvalidationConcept(
            kind=InvalidationType.VOLATILITY,
            price=invalidation_price,
            rationale=("momentum thesis fails beyond volatility or structural support",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.EXPANSION,
                    price=target_price,
                    label="primary",
                    rationale=("nearest opposing liquidity or expansion objective",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=frame.structure.trend.strength if has_trend else 0.7,
            structure_quality=0.8 if has_break else frame.structure.trend.strength,
            entry_quality=entry.location_quality,
            momentum_quality=aligned / total,
            volume_quality=_volume_quality(features.relative_volume),
            liquidity_quality=0.5,
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
                "directional trend or recent structural continuation is present",
                f"{aligned} of {total} available momentum measures align",
                "entry is immediate or a shallow continuation reference near CMP",
                "ATR-aware chase protection remains satisfied",
            ),
            warnings=warnings,
            feature_references=tuple(
                name
                for name, value in (
                    ("rate_of_change", features.rate_of_change),
                    ("macd_histogram", features.macd_histogram),
                    ("rsi_slope", features.rsi_slope),
                    ("relative_volume", features.relative_volume),
                    ("ema_fast", features.ema_fast),
                    ("vwap", features.vwap),
                )
                if value is not None
            ),
            structure_references=("trend", "breaks", "levels"),
        ),
        metadata={
            "decision_timeframe": frame.timeframe,
            "momentum_signal_count": total,
            "aligned_momentum_count": aligned,
            "recent_continuation_break": has_break,
        },
        provisional=context.provisional,
    )


def _has_recent_continuation_break(context: StrategyContext, *, bullish: bool) -> bool:
    direction = BreakDirection.BULLISH if bullish else BreakDirection.BEARISH
    return any(
        item.direction is direction
        and item.quality in {BreakQuality.VALID, BreakQuality.STRONG}
        and item.confirmation is ConfirmationStatus.CONFIRMED
        for item in context.decision_frame.structure.breaks
    )


def _momentum_alignment(context: StrategyContext, *, bullish: bool) -> tuple[int, int]:
    features = context.decision_frame.features
    signals = tuple(
        value
        for value in (
            features.rate_of_change,
            features.macd_histogram,
            features.rsi_slope,
        )
        if value is not None
    )
    aligned = sum(value > 0 if bullish else value < 0 for value in signals)
    return aligned, len(signals)


def _entry_references(
    context: StrategyContext,
    *,
    bullish: bool,
) -> tuple[EntryReference, ...]:
    features = context.decision_frame.features
    current = context.current_price
    raw = tuple(
        EntryReference(
            price=value,
            mode=EntryMode.MOMENTUM_CONTINUATION,
            rationale=(f"shallow {name} continuation reference improves entry geometry",),
        )
        for name, value in (("fast EMA", features.ema_fast), ("VWAP", features.vwap))
        if value is not None
        and ((bullish and value <= current) or (not bullish and value >= current))
    )
    return tuple(sorted(raw, key=lambda item: (abs(item.price - current), item.price)))


def _invalidation_price(context: StrategyContext, *, bullish: bool) -> float:
    frame = context.decision_frame
    current = context.current_price
    role = LevelRole.SUPPORT if bullish else LevelRole.RESISTANCE
    levels = [
        item.representative_price
        for item in frame.structure.levels
        if item.role is role
        and item.status is not LevelStatus.BROKEN
        and ((bullish and item.representative_price < current) or (not bullish and item.representative_price > current))
    ]
    if levels:
        anchor = max(levels) if bullish else min(levels)
        return anchor - context.atr * 0.2 if bullish else anchor + context.atr * 0.2
    return current - context.atr if bullish else current + context.atr


def _target_price(context: StrategyContext, *, bullish: bool) -> float:
    frame = context.decision_frame
    current = context.current_price
    role = LevelRole.RESISTANCE if bullish else LevelRole.SUPPORT
    levels = [
        item.representative_price
        for item in frame.structure.levels
        if item.role is role
        and item.status is not LevelStatus.BROKEN
        and ((bullish and item.representative_price > current) or (not bullish and item.representative_price < current))
    ]
    if levels:
        return min(levels) if bullish else max(levels)
    return current + context.atr * 2.2 if bullish else current - context.atr * 2.2


def _volume_quality(value: float | None) -> float:
    return 0.5 if value is None else min(1.0, value / 2.0)


def _target_space_quality(*, current: float, invalidation: float, target: float) -> float:
    risk = abs(current - invalidation)
    reward = abs(target - current)
    if risk <= 0:
        return 0.0
    return min(1.0, reward / risk / 3.0)


def _valid_geometry(*, current: float, invalidation: float, target: float, bullish: bool) -> bool:
    return invalidation < current < target if bullish else target < current < invalidation
