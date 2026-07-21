"""Deterministic trend-pullback candidate generation."""

from __future__ import annotations

from datetime import datetime

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
from apex.strategies.entry import (
    DEFAULT_ENTRY_SELECTION_CONFIG,
    EntryReference,
    EntrySelectionConfig,
    select_entry_zone,
)
from apex.strategies.strategy_types import StrategyType
from apex.strategies.target_quality import target_space_quality
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


def generate_trend_pullback_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
    entry_config: EntrySelectionConfig = DEFAULT_ENTRY_SELECTION_CONFIG,
) -> tuple[TradeCandidate, ...]:
    """Generate zero, one, or competing deterministic trend-pullback candidates."""

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
    higher_timeframe_conflict = context.higher_timeframe_contradiction(bullish=bullish)

    frame = context.decision_frame
    accepted_trends = _BULLISH_TRENDS if bullish else _BEARISH_TRENDS
    if frame.structure.trend.direction not in accepted_trends:
        return None
    if not _momentum_is_constructive(context, bullish=bullish):
        return None

    current = context.current_price
    atr = context.atr
    invalidation_price, invalidation_type = _invalidation_geometry(
        context,
        bullish=bullish,
    )
    target_price, target_type, target_rationale = _target_geometry(
        context,
        bullish=bullish,
    )
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
    support = [
        f"{frame.timeframe} structure is {frame.structure.trend.direction.value}",
        "price is evaluating a nearby trend support area"
        if bullish
        else "price is evaluating a nearby trend resistance area",
        "momentum cooled without invalidating the directional structure",
        "entry remains inside the volatility-aware near-CMP limit",
    ]
    warnings: list[str] = []
    if context.provisional:
        warnings.append("active-candle evidence is provisional")
    if higher_timeframe_conflict:
        warnings.append("higher-timeframe trend conflicts with the decision-frame pullback thesis")
    features = frame.features
    feature_refs = tuple(
        name
        for name, value in (
            ("ema_fast", features.ema_fast),
            ("ema_slow", features.ema_slow),
            ("vwap", features.vwap),
            ("rsi", features.rsi),
            ("rsi_slope", features.rsi_slope),
            ("macd_histogram", features.macd_histogram),
        )
        if value is not None
    )
    trend_strength = frame.structure.trend.strength
    momentum_quality = _momentum_quality(context, bullish=bullish)
    metadata: dict[str, str | int | float | bool] = {
        "decision_timeframe": frame.timeframe,
        "decision_atr": atr,
        "decision_atr_percentage": atr / current * 100.0,
        "reference_count": len(references),
        "higher_timeframe_conflict": higher_timeframe_conflict,
        "invalidation_includes_noise_buffer": True,
        "invalidation_buffer_source": "strategy_structure_or_volatility_stop",
        **_selected_entry_geometry_metadata(
            context,
            entry_lower=entry.lower,
            entry_upper=entry.upper,
            entry_preferred=entry.preferred,
            bullish=bullish,
        ),
    }
    return TradeCandidate(
        symbol=context.symbol,
        strategy=StrategyType.TREND_PULLBACK,
        direction=direction,
        decision_time=decision_time,
        entry=entry,
        invalidation=InvalidationConcept(
            kind=invalidation_type,
            price=invalidation_price,
            rationale=(
                "trade thesis fails beyond the nearest meaningful support"
                if bullish
                else "trade thesis fails beyond the nearest meaningful resistance",
            ),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=target_type,
                    price=target_price,
                    label="primary",
                    rationale=(target_rationale,),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=trend_strength,
            structure_quality=trend_strength,
            entry_quality=entry.location_quality,
            momentum_quality=momentum_quality,
            volume_quality=_optional_unit(features.relative_volume, neutral=0.5),
            liquidity_quality=0.5,
            target_space_quality=target_space_quality(
                current=current,
                invalidation=invalidation_price,
                target=target_price,
                target_type=target_type,
            ),
            extension_penalty=1.0 - entry.location_quality,
            conflict_penalty=0.25 if higher_timeframe_conflict else 0.0,
        ),
        evidence=StrategyEvidence(
            supporting=tuple(support),
            warnings=tuple(warnings),
            feature_references=feature_refs,
            structure_references=("trend", "levels"),
        ),
        metadata=metadata,
        provisional=context.provisional,
    )


def _entry_references(
    context: StrategyContext,
    *,
    bullish: bool,
) -> tuple[EntryReference, ...]:
    frame = context.decision_frame
    current = context.current_price
    raw: list[EntryReference] = []
    for name, value in (
        ("fast EMA", frame.features.ema_fast),
        ("slow EMA", frame.features.ema_slow),
        ("VWAP", frame.features.vwap),
    ):
        if value is None:
            continue
        if (bullish and value <= current) or (not bullish and value >= current):
            raw.append(
                EntryReference(
                    price=value,
                    mode=EntryMode.PULLBACK,
                    rationale=(f"nearby {name} retest improves trend-pullback location",),
                )
            )
    expected_role = LevelRole.SUPPORT if bullish else LevelRole.RESISTANCE
    for level in frame.structure.levels:
        if level.role is not expected_role or level.status is LevelStatus.BROKEN:
            continue
        price = level.representative_price
        if (bullish and price <= current) or (not bullish and price >= current):
            raw.append(
                EntryReference(
                    price=price,
                    mode=EntryMode.RETEST,
                    rationale=("nearby structural level offers a defined retest",),
                    scaled=level.low < level.high,
                    zone_lower=level.low,
                    zone_upper=level.high,
                    trigger_price=level.representative_price,
                )
            )
    unique = {(item.price, item.mode.value, item.scaled): item for item in raw}
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (abs(item.price - current), item.price, item.mode.value),
        )
    )


def _selected_entry_geometry_metadata(
    context: StrategyContext,
    *,
    entry_lower: float,
    entry_upper: float,
    entry_preferred: float,
    bullish: bool,
) -> dict[str, str | int | float | bool]:
    """Describe the selected structural retest without inventing breakout data."""

    expected_role = LevelRole.SUPPORT if bullish else LevelRole.RESISTANCE
    matching = tuple(
        level
        for level in context.decision_frame.structure.levels
        if level.role is expected_role
        and level.status is not LevelStatus.BROKEN
        and level.low <= entry_preferred <= level.high
        and entry_lower <= level.representative_price <= entry_upper
    )
    if not matching:
        return {
            "entry_geometry_owner": "shared_entry_selector",
            "structural_retest_geometry_available": False,
        }

    selected = min(
        matching,
        key=lambda level: (
            abs(level.representative_price - entry_preferred),
            level.high - level.low,
            level.representative_price,
        ),
    )
    return {
        "entry_geometry_owner": "strategy_structure_level",
        "structural_retest_geometry_available": True,
        "retest_zone_low": selected.low,
        "retest_zone_high": selected.high,
        "retest_preferred_entry": selected.representative_price,
        "retest_trigger_level": selected.representative_price,
        "retest_penetration_allowance": selected.high - selected.low,
        "retest_confirmation_rule": (
            "hold_or_reclaim_above_retest_zone" if bullish else "hold_or_reject_below_retest_zone"
        ),
        "breakout_level_available": False,
    }


def _invalidation_geometry(
    context: StrategyContext,
    *,
    bullish: bool,
) -> tuple[float, InvalidationType]:
    frame = context.decision_frame
    current = context.current_price
    role = LevelRole.SUPPORT if bullish else LevelRole.RESISTANCE
    eligible = [
        level.representative_price
        for level in frame.structure.levels
        if level.role is role
        and level.status is not LevelStatus.BROKEN
        and (
            (bullish and level.representative_price < current)
            or (not bullish and level.representative_price > current)
        )
    ]
    if eligible:
        anchor = max(eligible) if bullish else min(eligible)
        buffered = anchor - context.atr * 0.2 if bullish else anchor + context.atr * 0.2
        return buffered, InvalidationType.STRUCTURAL
    fallback = current - context.atr * 1.2 if bullish else current + context.atr * 1.2
    return fallback, InvalidationType.VOLATILITY


def _target_geometry(
    context: StrategyContext,
    *,
    bullish: bool,
) -> tuple[float, TargetType, str]:
    frame = context.decision_frame
    current = context.current_price
    role = LevelRole.RESISTANCE if bullish else LevelRole.SUPPORT
    eligible = [
        level.representative_price
        for level in frame.structure.levels
        if level.role is role
        and level.status is not LevelStatus.BROKEN
        and (
            (bullish and level.representative_price > current)
            or (not bullish and level.representative_price < current)
        )
    ]
    if eligible:
        return (
            min(eligible) if bullish else max(eligible),
            TargetType.STRUCTURAL,
            (
                "nearest observed opposing structural resistance"
                if bullish
                else "nearest observed opposing structural support"
            ),
        )
    projected = current + context.atr * 2.4 if bullish else current - context.atr * 2.4
    return (
        projected,
        TargetType.EXPANSION,
        "2.4 ATR expansion projection; no verified opposing structure was available",
    )


def _momentum_is_constructive(context: StrategyContext, *, bullish: bool) -> bool:
    features = context.decision_frame.features
    if features.rsi is not None and not 30 <= features.rsi <= 70:
        return False
    directional = tuple(
        value
        for value in (
            features.rsi_slope,
            features.macd_histogram,
            features.rate_of_change,
        )
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


def _optional_unit(value: float | None, *, neutral: float) -> float:
    if value is None:
        return neutral
    return min(1.0, value / 2.0)


def _valid_geometry(*, current: float, invalidation: float, target: float, bullish: bool) -> bool:
    return invalidation < current < target if bullish else target < current < invalidation
