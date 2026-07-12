"""Deterministic range-reversal candidate generation."""

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
from apex.strategies.entry import (
    DEFAULT_ENTRY_SELECTION_CONFIG,
    EntryReference,
    EntrySelectionConfig,
    select_entry_zone,
)
from apex.structure.contracts import RangeBreakoutState, RangeStructure, TrendDirection

_MINIMUM_RANGE_QUALITY = 0.6
_EDGE_FRACTION = 0.35


def generate_range_reversal_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
    entry_config: EntrySelectionConfig = DEFAULT_ENTRY_SELECTION_CONFIG,
    minimum_range_quality: float = _MINIMUM_RANGE_QUALITY,
) -> tuple[TradeCandidate, ...]:
    """Generate valid range-edge reversals in stable direction order."""

    candidates = tuple(
        candidate
        for direction in (TradeDirection.LONG, TradeDirection.SHORT)
        if (
            candidate := _candidate_for_direction(
                context,
                direction=direction,
                decision_time=decision_time,
                entry_config=entry_config,
                minimum_range_quality=minimum_range_quality,
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
    minimum_range_quality: float,
) -> TradeCandidate | None:
    bullish = direction is TradeDirection.LONG
    frame = context.decision_frame
    detected_range = _best_range(context, minimum_quality=minimum_range_quality)
    if detected_range is None:
        return None
    if context.higher_timeframe_contradiction(bullish=bullish):
        return None
    if not _trend_allows_mean_reversion(frame.structure.trend.direction):
        return None
    if not _breakout_state_allows(detected_range.breakout_state, bullish=bullish):
        return None
    if not _near_relevant_edge(detected_range, bullish=bullish):
        return None
    if not _momentum_allows(context, bullish=bullish):
        return None

    current = context.current_price
    atr = context.atr
    boundary = detected_range.low if bullish else detected_range.high
    invalidation_price = boundary - atr * 0.2 if bullish else boundary + atr * 0.2
    targets = _targets(detected_range, current=current, bullish=bullish)
    if not targets:
        return None
    primary_target = targets[-1].price
    if not _valid_geometry(
        current=current,
        invalidation=invalidation_price,
        target=primary_target,
        bullish=bullish,
    ):
        return None

    entry = select_entry_zone(
        current_price=current,
        atr=atr,
        direction=direction,
        invalidation_price=invalidation_price,
        target_price=primary_target,
        references=(
            EntryReference(
                price=boundary,
                mode=EntryMode.RETEST,
                rationale=("range boundary offers a defined mean-reversion entry",),
                scaled=True,
            ),
        ),
        config=entry_config,
    )
    features = frame.features
    warnings = ("active-candle evidence is provisional",) if context.provisional else ()
    false_break = detected_range.breakout_state in {
        RangeBreakoutState.FALSE_BULLISH,
        RangeBreakoutState.FALSE_BEARISH,
    }
    supporting = [
        f"{frame.timeframe} range quality is {detected_range.quality:.3f}",
        (
            "price is located near the lower range boundary"
            if bullish
            else "price is located near the upper range boundary"
        ),
        "range geometry provides space for mean reversion",
        "entry remains inside the volatility-aware near-CMP limit",
    ]
    if false_break:
        supporting.append("confirmed false-break state supports rejection back into the range")

    return TradeCandidate(
        symbol=context.symbol,
        strategy=StrategyType.RANGE_REVERSAL,
        direction=direction,
        decision_time=decision_time,
        entry=entry,
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=invalidation_price,
            rationale=("range thesis fails outside the relevant boundary",),
        ),
        targets=TargetConcept(levels=targets),
        quality=RawQualityMetrics(
            trend_alignment=0.5,
            structure_quality=detected_range.quality,
            entry_quality=entry.location_quality,
            momentum_quality=_momentum_quality(context, bullish=bullish),
            volume_quality=_optional_unit(features.relative_volume, neutral=0.5),
            liquidity_quality=0.8 if false_break else 0.5,
            target_space_quality=_target_space_quality(
                current=current,
                invalidation=invalidation_price,
                target=primary_target,
            ),
            extension_penalty=1.0 - entry.location_quality,
            conflict_penalty=0.0,
        ),
        evidence=StrategyEvidence(
            supporting=tuple(supporting),
            warnings=warnings,
            feature_references=tuple(
                name
                for name, value in (
                    ("range_position", features.range_position),
                    ("rsi", features.rsi),
                    ("rsi_slope", features.rsi_slope),
                    ("macd_histogram", features.macd_histogram),
                    ("rate_of_change", features.rate_of_change),
                    ("relative_volume", features.relative_volume),
                )
                if value is not None
            ),
            structure_references=("range",),
        ),
        metadata={
            "decision_timeframe": frame.timeframe,
            "range_start_index": detected_range.start_index,
            "range_end_index": detected_range.end_index,
            "range_quality": detected_range.quality,
        },
        provisional=context.provisional,
    )


def _best_range(context: StrategyContext, *, minimum_quality: float) -> RangeStructure | None:
    eligible = tuple(
        item for item in context.decision_frame.structure.ranges if item.quality >= minimum_quality
    )
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda item: (
            -item.end_index,
            -item.quality,
            item.start_index,
            item.low,
            item.high,
        ),
    )


def _trend_allows_mean_reversion(direction: TrendDirection) -> bool:
    return direction in {
        TrendDirection.RANGE,
        TrendDirection.TRANSITION,
        TrendDirection.UNCERTAIN,
        TrendDirection.WEAK_BULLISH,
        TrendDirection.WEAK_BEARISH,
    }


def _breakout_state_allows(state: RangeBreakoutState, *, bullish: bool) -> bool:
    invalid = RangeBreakoutState.BEARISH if bullish else RangeBreakoutState.BULLISH
    return state is not invalid


def _near_relevant_edge(detected_range: RangeStructure, *, bullish: bool) -> bool:
    position = detected_range.current_position
    return position <= _EDGE_FRACTION if bullish else position >= 1.0 - _EDGE_FRACTION


def _momentum_allows(context: StrategyContext, *, bullish: bool) -> bool:
    features = context.decision_frame.features
    if features.rsi is not None:
        if bullish and features.rsi > 60:
            return False
        if not bullish and features.rsi < 40:
            return False
    signals = tuple(
        value
        for value in (
            features.rsi_slope,
            features.macd_histogram,
            features.rate_of_change,
        )
        if value is not None
    )
    if not signals:
        return True
    opposed = sum(value < 0 if bullish else value > 0 for value in signals)
    return opposed < len(signals)


def _momentum_quality(context: StrategyContext, *, bullish: bool) -> float:
    features = context.decision_frame.features
    signals = tuple(
        value
        for value in (
            features.rsi_slope,
            features.macd_histogram,
            features.rate_of_change,
        )
        if value is not None
    )
    if not signals:
        return 0.5
    aligned = sum(value >= 0 if bullish else value <= 0 for value in signals)
    return aligned / len(signals)


def _targets(
    detected_range: RangeStructure,
    *,
    current: float,
    bullish: bool,
) -> tuple[TargetLevel, ...]:
    raw = (
        (
            TargetType.PARTIAL,
            detected_range.midpoint,
            "midpoint",
            "range midpoint is the first mean-reversion objective",
        ),
        (
            TargetType.RANGE,
            detected_range.high if bullish else detected_range.low,
            "opposite_boundary",
            "opposite range boundary is the primary expansion objective",
        ),
    )
    valid = tuple(
        TargetLevel(kind=kind, price=price, label=label, rationale=(rationale,))
        for kind, price, label, rationale in raw
        if (bullish and price > current) or (not bullish and price < current)
    )
    return tuple(sorted(valid, key=lambda level: level.price, reverse=not bullish))


def _target_space_quality(*, current: float, invalidation: float, target: float) -> float:
    risk = abs(current - invalidation)
    reward = abs(target - current)
    if risk <= 0:
        return 0.0
    return min(1.0, reward / risk / 3.0)


def _optional_unit(value: float | None, *, neutral: float) -> float:
    if value is None:
        return neutral
    return min(1.0, value / 2.0)


def _valid_geometry(*, current: float, invalidation: float, target: float, bullish: bool) -> bool:
    return invalidation < current < target if bullish else target < current < invalidation
