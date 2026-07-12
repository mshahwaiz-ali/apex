"""Deterministic breakout-continuation candidate generation."""

from __future__ import annotations

from datetime import datetime

from apex.liquidity.contracts import LiquiditySide, LiquidityZoneStatus
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
from apex.strategies.entry import (
    DEFAULT_ENTRY_SELECTION_CONFIG,
    EntryReference,
    EntrySelectionConfig,
    select_entry_zone,
)
from apex.structure.contracts import (
    BreakDirection,
    BreakQuality,
    ConfirmationStatus,
    LevelRole,
    LevelStatus,
    StructureBreak,
)


def generate_breakout_continuation_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
    entry_config: EntrySelectionConfig = DEFAULT_ENTRY_SELECTION_CONFIG,
    minimum_relative_volume: float = 1.0,
    maximum_extension_atr: float = 1.25,
) -> tuple[TradeCandidate, ...]:
    """Generate confirmed breakout-continuation candidates in stable order."""

    candidates = tuple(
        candidate
        for direction in (TradeDirection.LONG, TradeDirection.SHORT)
        if (
            candidate := _candidate_for_direction(
                context,
                direction=direction,
                decision_time=decision_time,
                entry_config=entry_config,
                minimum_relative_volume=minimum_relative_volume,
                maximum_extension_atr=maximum_extension_atr,
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
    minimum_relative_volume: float,
    maximum_extension_atr: float,
) -> TradeCandidate | None:
    bullish = direction is TradeDirection.LONG
    if context.higher_timeframe_contradiction(bullish=bullish):
        return None

    frame = context.decision_frame
    break_event = _latest_confirmed_break(frame.structure.breaks, bullish=bullish)
    if break_event is None:
        return None

    features = frame.features
    if features.relative_volume is not None and features.relative_volume < minimum_relative_volume:
        return None
    if not _momentum_supports_breakout(context, bullish=bullish):
        return None

    current = context.current_price
    atr = context.atr
    extension_atr = abs(current - break_event.broken_level) / atr
    if extension_atr > maximum_extension_atr:
        return None
    if bullish and current <= break_event.broken_level:
        return None
    if not bullish and current >= break_event.broken_level:
        return None

    invalidation_price = (
        break_event.broken_level - atr * 0.15 if bullish else break_event.broken_level + atr * 0.15
    )
    target_price = _target_price(context, bullish=bullish)
    if not _valid_geometry(
        current=current,
        invalidation=invalidation_price,
        target=target_price,
        bullish=bullish,
    ):
        return None

    entry = select_entry_zone(
        current_price=current,
        atr=atr,
        direction=direction,
        invalidation_price=invalidation_price,
        target_price=target_price,
        references=(
            EntryReference(
                price=break_event.broken_level,
                mode=EntryMode.RETEST,
                rationale=("nearby broken-level retest improves breakout entry quality",),
            ),
        ),
        config=entry_config,
    )
    warnings = ("active-candle evidence is provisional",) if context.provisional else ()
    volume_quality = (
        0.5 if features.relative_volume is None else min(1.0, features.relative_volume / 2.0)
    )
    breakout_quality = 1.0 if break_event.quality is BreakQuality.STRONG else 0.8
    return TradeCandidate(
        symbol=context.symbol,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        direction=direction,
        decision_time=decision_time,
        entry=entry,
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=invalidation_price,
            rationale=("breakout thesis fails if price reclaims the broken level",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.LIQUIDITY,
                    price=target_price,
                    label="primary",
                    rationale=("nearest opposing liquidity or structural objective",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=frame.structure.trend.strength,
            structure_quality=breakout_quality,
            entry_quality=entry.location_quality,
            momentum_quality=_momentum_quality(context, bullish=bullish),
            volume_quality=volume_quality,
            liquidity_quality=0.6,
            target_space_quality=_target_space_quality(
                current=current,
                invalidation=invalidation_price,
                target=target_price,
            ),
            extension_penalty=min(1.0, extension_atr / maximum_extension_atr),
            conflict_penalty=0.0,
        ),
        evidence=StrategyEvidence(
            supporting=(
                f"confirmed {break_event.quality.value} structural breakout",
                "breakout close remains within the anti-chase extension limit",
                "entry uses immediate continuation or a nearby broken-level retest",
            ),
            warnings=warnings,
            feature_references=tuple(
                name
                for name, value in (
                    ("relative_volume", features.relative_volume),
                    ("macd_histogram", features.macd_histogram),
                    ("rate_of_change", features.rate_of_change),
                )
                if value is not None
            ),
            structure_references=("breaks", "levels"),
            liquidity_references=("zones",),
        ),
        metadata={
            "break_candle_index": break_event.candle_index,
            "break_quality": break_event.quality.value,
            "extension_atr": extension_atr,
        },
        provisional=context.provisional,
    )


def _latest_confirmed_break(
    breaks: tuple[StructureBreak, ...],
    *,
    bullish: bool,
) -> StructureBreak | None:
    direction = BreakDirection.BULLISH if bullish else BreakDirection.BEARISH
    eligible = tuple(
        event
        for event in breaks
        if event.direction is direction
        and event.quality in {BreakQuality.VALID, BreakQuality.STRONG}
        and event.confirmation is ConfirmationStatus.CONFIRMED
    )
    return max(eligible, key=lambda event: event.candle_index, default=None)


def _momentum_supports_breakout(context: StrategyContext, *, bullish: bool) -> bool:
    features = context.decision_frame.features
    signals = tuple(
        value
        for value in (features.macd_histogram, features.rate_of_change, features.rsi_slope)
        if value is not None
    )
    if not signals:
        return True
    return any(value >= 0 for value in signals) if bullish else any(value <= 0 for value in signals)


def _momentum_quality(context: StrategyContext, *, bullish: bool) -> float:
    features = context.decision_frame.features
    signals = tuple(
        value
        for value in (features.macd_histogram, features.rate_of_change, features.rsi_slope)
        if value is not None
    )
    if not signals:
        return 0.5
    aligned = sum(value >= 0 if bullish else value <= 0 for value in signals)
    return aligned / len(signals)


def _target_price(context: StrategyContext, *, bullish: bool) -> float:
    frame = context.decision_frame
    current = context.current_price
    liquidity_side = LiquiditySide.BUY_SIDE if bullish else LiquiditySide.SELL_SIDE
    liquidity_prices = [
        zone.representative_price
        for zone in frame.liquidity.zones
        if zone.side is liquidity_side
        and zone.status is LiquidityZoneStatus.ACTIVE
        and (
            (bullish and zone.representative_price > current)
            or (not bullish and zone.representative_price < current)
        )
    ]
    if liquidity_prices:
        return min(liquidity_prices) if bullish else max(liquidity_prices)

    role = LevelRole.RESISTANCE if bullish else LevelRole.SUPPORT
    level_prices = [
        level.representative_price
        for level in frame.structure.levels
        if level.role is role
        and level.status is not LevelStatus.BROKEN
        and (
            (bullish and level.representative_price > current)
            or (not bullish and level.representative_price < current)
        )
    ]
    if level_prices:
        return min(level_prices) if bullish else max(level_prices)
    return current + context.atr * 2.5 if bullish else current - context.atr * 2.5


def _target_space_quality(*, current: float, invalidation: float, target: float) -> float:
    risk = abs(current - invalidation)
    reward = abs(target - current)
    if risk <= 0:
        return 0.0
    return min(1.0, reward / risk / 3.0)


def _valid_geometry(*, current: float, invalidation: float, target: float, bullish: bool) -> bool:
    return invalidation < current < target if bullish else target < current < invalidation
