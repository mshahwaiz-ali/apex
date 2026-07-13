"""Deterministic continuation strategy for unusually strong directional movers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from apex.strategies.context import StrategyContext, TimeframeRole
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
from apex.strategies.entry import (
    DEFAULT_ENTRY_SELECTION_CONFIG,
    EntryReference,
    EntrySelectionConfig,
    select_entry_zone,
)
from apex.structure.contracts import LevelRole, LevelStatus, TrendDirection

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
_HIGHER_ROLES = {
    TimeframeRole.LONG_TERM_MACRO,
    TimeframeRole.SWING,
    TimeframeRole.MACRO,
    TimeframeRole.INTERMEDIATE,
}


@dataclass(frozen=True, slots=True)
class MomentumGainerContinuationConfig:
    """Named structural thresholds for strong-mover continuation candidates."""

    minimum_absolute_roc: float = 0.02
    minimum_relative_volume: float = 1.25
    minimum_trend_persistence: float = 0.65
    minimum_momentum_alignment: float = 2 / 3
    minimum_higher_timeframe_alignment: float = 0.5
    minimum_range_position_long: float = 0.60
    maximum_range_position_short: float = 0.40
    maximum_volatility_expansion: float = 0.85
    maximum_extension_atr: float = 1.25
    minimum_target_r_multiple: float = 1.5
    stop_buffer_atr: float = 0.20
    fallback_stop_atr: float = 1.0
    fallback_target_atr: float = 2.2

    def __post_init__(self) -> None:
        names = (
            "minimum_absolute_roc",
            "minimum_relative_volume",
            "minimum_trend_persistence",
            "minimum_momentum_alignment",
            "minimum_higher_timeframe_alignment",
            "minimum_range_position_long",
            "maximum_range_position_short",
            "maximum_volatility_expansion",
            "maximum_extension_atr",
            "minimum_target_r_multiple",
            "stop_buffer_atr",
            "fallback_stop_atr",
            "fallback_target_atr",
        )
        for name in names:
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name.replace('_', ' ')} must be finite and non-negative")
        unit_names = (
            "minimum_trend_persistence",
            "minimum_momentum_alignment",
            "minimum_higher_timeframe_alignment",
            "minimum_range_position_long",
            "maximum_range_position_short",
            "maximum_volatility_expansion",
        )
        for name in unit_names:
            if getattr(self, name) > 1:
                raise ValueError(f"{name.replace('_', ' ')} must not exceed one")


DEFAULT_MOMENTUM_GAINER_CONTINUATION_CONFIG = MomentumGainerContinuationConfig()


def generate_momentum_gainer_continuation_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
    config: MomentumGainerContinuationConfig = DEFAULT_MOMENTUM_GAINER_CONTINUATION_CONFIG,
    entry_config: EntrySelectionConfig = DEFAULT_ENTRY_SELECTION_CONFIG,
) -> tuple[TradeCandidate, ...]:
    """Generate long and short strong-mover continuation candidates deterministically."""

    candidates = tuple(
        candidate
        for direction in (TradeDirection.LONG, TradeDirection.SHORT)
        if (
            candidate := _candidate_for_direction(
                context,
                direction=direction,
                decision_time=decision_time,
                config=config,
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
    config: MomentumGainerContinuationConfig,
    entry_config: EntrySelectionConfig,
) -> TradeCandidate | None:
    bullish = direction is TradeDirection.LONG
    frame = context.decision_frame
    features = frame.features
    accepted = _BULLISH_TRENDS if bullish else _BEARISH_TRENDS
    if frame.structure.trend.direction not in accepted:
        return None
    if context.higher_timeframe_contradiction(bullish=bullish):
        return None

    roc = features.rate_of_change
    relative_volume = features.relative_volume
    persistence = frame.structure.trend.evidence.persistence
    if roc is None or relative_volume is None:
        return None
    if bullish and roc < config.minimum_absolute_roc:
        return None
    if not bullish and roc > -config.minimum_absolute_roc:
        return None
    if relative_volume < config.minimum_relative_volume:
        return None
    if persistence < config.minimum_trend_persistence:
        return None

    aligned, total = _momentum_alignment(context, bullish=bullish)
    if total == 0 or aligned / total < config.minimum_momentum_alignment:
        return None
    higher_alignment = _higher_timeframe_alignment(context, bullish=bullish)
    if higher_alignment < config.minimum_higher_timeframe_alignment:
        return None
    if not _continuation_location_is_orderly(context, bullish=bullish, config=config):
        return None

    current = context.current_price
    extension_atr = _reference_extension_atr(context, bullish=bullish)
    if extension_atr > config.maximum_extension_atr:
        return None
    invalidation_price = _invalidation_price(context, bullish=bullish, config=config)
    target_price = _target_price(context, bullish=bullish, config=config)
    if not _valid_geometry(
        current=current,
        invalidation=invalidation_price,
        target=target_price,
        bullish=bullish,
    ):
        return None
    target_r = abs(target_price - current) / abs(current - invalidation_price)
    if target_r < config.minimum_target_r_multiple:
        return None

    entry = select_entry_zone(
        current_price=current,
        atr=context.atr,
        direction=direction,
        invalidation_price=invalidation_price,
        target_price=target_price,
        references=_entry_references(context, bullish=bullish),
        config=entry_config,
    )
    if entry.is_extended:
        return None

    warnings = ("active-candle evidence is provisional",) if context.provisional else ()
    location_quality = _location_quality(context, bullish=bullish)
    return TradeCandidate(
        symbol=context.symbol,
        strategy=StrategyType.MOMENTUM_GAINER_CONTINUATION,
        direction=direction,
        decision_time=decision_time,
        entry=entry,
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=invalidation_price,
            rationale=("continuation thesis fails beyond the retained structural base",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.LIQUIDITY,
                    price=target_price,
                    label="primary",
                    rationale=("nearest opposing structure or ATR expansion objective",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=(frame.structure.trend.strength + higher_alignment) / 2,
            structure_quality=min(1.0, (persistence + location_quality) / 2),
            entry_quality=entry.location_quality,
            momentum_quality=aligned / total,
            volume_quality=min(1.0, relative_volume / 2.0),
            liquidity_quality=min(1.0, target_r / 3.0),
            target_space_quality=min(1.0, target_r / 3.0),
            extension_penalty=min(1.0, extension_atr / config.maximum_extension_atr),
            conflict_penalty=0.0,
        ),
        evidence=StrategyEvidence(
            supporting=(
                f"directional expansion ROC is {roc:.4f}",
                f"relative volume is {relative_volume:.2f}x",
                f"trend persistence is {persistence:.2f}",
                f"{aligned} of {total} momentum measures remain aligned",
                f"higher-timeframe alignment is {higher_alignment:.2f}",
                f"nearest target provides {target_r:.2f}R before the primary obstacle",
            ),
            warnings=warnings,
            feature_references=tuple(
                name
                for name, value in (
                    ("rate_of_change", roc),
                    ("relative_volume", relative_volume),
                    ("macd_histogram", features.macd_histogram),
                    ("rsi_slope", features.rsi_slope),
                    ("range_position", features.range_position),
                    ("volatility_expansion", features.volatility_expansion),
                    ("ema_fast", features.ema_fast),
                    ("vwap", features.vwap),
                )
                if value is not None
            ),
            structure_references=("trend", "levels"),
            liquidity_references=("nearest opposing structural obstacle",),
        ),
        metadata={
            "decision_timeframe": frame.timeframe,
            "expansion_roc": roc,
            "relative_volume": relative_volume,
            "trend_persistence": persistence,
            "momentum_signal_count": total,
            "aligned_momentum_count": aligned,
            "higher_timeframe_alignment": higher_alignment,
            "reference_extension_atr": extension_atr,
            "target_r_multiple": target_r,
            "continuation_pattern": "upper_range_hold" if bullish else "lower_range_hold",
        },
        provisional=context.provisional,
    )


def _momentum_alignment(context: StrategyContext, *, bullish: bool) -> tuple[int, int]:
    features = context.decision_frame.features
    signals = tuple(
        value
        for value in (features.rate_of_change, features.macd_histogram, features.rsi_slope)
        if value is not None
    )
    return sum(value > 0 if bullish else value < 0 for value in signals), len(signals)


def _higher_timeframe_alignment(context: StrategyContext, *, bullish: bool) -> float:
    frames = tuple(frame for frame in context.frames if frame.role in _HIGHER_ROLES)
    if not frames:
        return 1.0
    accepted = _BULLISH_TRENDS if bullish else _BEARISH_TRENDS
    return sum(
        frame.structure.trend.strength
        for frame in frames
        if frame.structure.trend.direction in accepted
    ) / len(frames)


def _continuation_location_is_orderly(
    context: StrategyContext,
    *,
    bullish: bool,
    config: MomentumGainerContinuationConfig,
) -> bool:
    features = context.decision_frame.features
    if (
        features.volatility_expansion is not None
        and features.volatility_expansion > config.maximum_volatility_expansion
    ):
        return False
    if features.range_position is None:
        return True
    if bullish:
        return features.range_position >= config.minimum_range_position_long
    return features.range_position <= config.maximum_range_position_short


def _reference_extension_atr(context: StrategyContext, *, bullish: bool) -> float:
    features = context.decision_frame.features
    references = tuple(
        value
        for value in (features.ema_fast, features.vwap)
        if value is not None
        and (
            (bullish and value <= context.current_price)
            or (not bullish and value >= context.current_price)
        )
    )
    if not references:
        return 0.0
    nearest = min(references, key=lambda value: abs(value - context.current_price))
    return abs(context.current_price - nearest) / context.atr


def _entry_references(
    context: StrategyContext,
    *,
    bullish: bool,
) -> tuple[EntryReference, ...]:
    current = context.current_price
    features = context.decision_frame.features
    references = tuple(
        EntryReference(
            price=value,
            mode=EntryMode.MOMENTUM_CONTINUATION,
            rationale=(f"retained {name} reference supports a controlled continuation entry",),
        )
        for name, value in (("fast EMA", features.ema_fast), ("VWAP", features.vwap))
        if value is not None
        and ((bullish and value <= current) or (not bullish and value >= current))
    )
    return tuple(sorted(references, key=lambda item: (abs(item.price - current), item.price)))


def _invalidation_price(
    context: StrategyContext,
    *,
    bullish: bool,
    config: MomentumGainerContinuationConfig,
) -> float:
    current = context.current_price
    role = LevelRole.SUPPORT if bullish else LevelRole.RESISTANCE
    levels = tuple(
        item.representative_price
        for item in context.decision_frame.structure.levels
        if item.role is role
        and item.status is not LevelStatus.BROKEN
        and (
            (bullish and item.representative_price < current)
            or (not bullish and item.representative_price > current)
        )
    )
    if levels:
        anchor = max(levels) if bullish else min(levels)
        buffer = context.atr * config.stop_buffer_atr
        return anchor - buffer if bullish else anchor + buffer
    fallback = context.atr * config.fallback_stop_atr
    return current - fallback if bullish else current + fallback


def _target_price(
    context: StrategyContext,
    *,
    bullish: bool,
    config: MomentumGainerContinuationConfig,
) -> float:
    current = context.current_price
    role = LevelRole.RESISTANCE if bullish else LevelRole.SUPPORT
    levels = tuple(
        item.representative_price
        for item in context.decision_frame.structure.levels
        if item.role is role
        and item.status is not LevelStatus.BROKEN
        and (
            (bullish and item.representative_price > current)
            or (not bullish and item.representative_price < current)
        )
    )
    if levels:
        return min(levels) if bullish else max(levels)
    fallback = context.atr * config.fallback_target_atr
    return current + fallback if bullish else current - fallback


def _location_quality(context: StrategyContext, *, bullish: bool) -> float:
    position = context.decision_frame.features.range_position
    if position is None:
        return 0.5
    return position if bullish else 1.0 - position


def _valid_geometry(*, current: float, invalidation: float, target: float, bullish: bool) -> bool:
    return invalidation < current < target if bullish else target < current < invalidation
