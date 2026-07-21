"""Deterministic momentum-continuation candidate generation."""

from __future__ import annotations

from datetime import datetime

from apex.strategies.context import StrategyContext
from apex.strategies.continuation_freshness import (
    ContinuationFreshness,
    measure_continuation_freshness,
)
from apex.strategies.continuation_participation import (
    ContinuationParticipation,
    ParticipationState,
    assess_continuation_participation,
)
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
    find_entry_zones,
)
from apex.strategies.strategy_types import StrategyType
from apex.strategies.target_quality import target_space_quality
from apex.structure.contracts import (
    BreakDirection,
    BreakQuality,
    ConfirmationStatus,
    LevelRole,
    LevelStatus,
    TrendDirection,
)

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
    entry_config: EntrySelectionConfig = DEFAULT_ENTRY_SELECTION_CONFIG,
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
    higher_timeframe_conflict = context.higher_timeframe_contradiction(bullish=bullish)

    aligned, total = _momentum_alignment(context, bullish=bullish)
    if total == 0 or aligned == 0:
        return None
    if aligned * 2 < total:
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

    freshness = _continuation_freshness(
        context,
        direction=direction,
        current=current,
        target=target_price,
    )
    if freshness is not None and not freshness.allows_new_continuation:
        return None

    references = _entry_references(context, bullish=bullish)
    entry_confirmation_complete = (
        has_break
        and aligned * 2 >= total
        and not context.provisional
        and not (freshness is not None and freshness.requires_conditional_entry)
    )
    try:
        entry_opportunities = find_entry_zones(
            current_price=current,
            atr=atr,
            direction=direction,
            invalidation_price=invalidation_price,
            target_price=target_price,
            references=references,
            config=entry_config,
            # Preserve a structurally valid setup even when execution confirmation
            # is incomplete. Actionability classification prevents an unconfirmed
            # market-near entry from being labelled READY_NOW.
            allow_market_entry=True,
            tick_size=frame.exchange_tick_size,
            spread_percentage=max(
                value
                for value in (
                    frame.spread_percentage,
                    frame.order_book_spread_percentage,
                    0.0,
                )
                if value is not None
            ),
        )
    except ValueError:
        return None
    entry = entry_opportunities[0]

    features = frame.features
    participation = assess_continuation_participation(
        direction=direction,
        features=features,
        market_evidence=context.market_evidence,
    )
    warnings: list[str] = []
    if participation.state is ParticipationState.CONTRADICTORY:
        warnings.append("available participation evidence contradicts continuation quality")
    if context.provisional:
        warnings.append("active-candle evidence is provisional")
    if entry.is_extended:
        warnings.append(
            "current execution is extended; preserve the setup for pullback, retest, "
            "or renewed confirmation rather than chasing"
        )
    if freshness is not None and freshness.requires_conditional_entry:
        warnings.append(
            "continuation is mature; preserve only a conditional pullback or renewed trigger"
        )
    if not entry_confirmation_complete:
        warnings.append(
            "setup structure remains valid but current-price execution confirmation is incomplete"
        )
    if higher_timeframe_conflict:
        warnings.append("higher-timeframe trend conflicts with the decision-frame momentum thesis")
    return TradeCandidate(
        symbol=context.symbol,
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        direction=direction,
        decision_time=decision_time,
        entry=entry,
        invalidation=InvalidationConcept(
            kind=invalidation_type,
            price=invalidation_price,
            rationale=("momentum thesis fails beyond volatility or structural support",),
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
            trend_alignment=frame.structure.trend.strength if has_trend else 0.7,
            structure_quality=0.8 if has_break else frame.structure.trend.strength,
            entry_quality=entry.location_quality,
            momentum_quality=aligned / total,
            volume_quality=_volume_quality(features.relative_volume),
            liquidity_quality=0.5,
            target_space_quality=target_space_quality(
                current=current,
                invalidation=invalidation_price,
                target=target_price,
                target_type=target_type,
            ),
            extension_penalty=max(
                1.0 - entry.location_quality,
                _freshness_extension_penalty(freshness),
            ),
            conflict_penalty=0.25 if higher_timeframe_conflict else 0.0,
        ),
        evidence=StrategyEvidence(
            supporting=(
                "directional trend or recent structural continuation is present",
                f"{aligned} of {total} available momentum measures align",
                "entry is immediate or a shallow continuation reference near CMP",
                "ATR-aware chase protection remains satisfied",
                *(() if freshness is None else freshness.reasons),
                *participation.reasons,
            ),
            warnings=tuple(warnings),
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
            **_freshness_metadata(freshness),
            **_participation_metadata(participation),
            "entry_opportunity_count": len(entry_opportunities),
            "momentum_signal_count": total,
            "aligned_momentum_count": aligned,
            "recent_continuation_break": has_break,
            "higher_timeframe_conflict": higher_timeframe_conflict,
            "entry_confirmation_complete": entry_confirmation_complete,
            "entry_confirmation_reason": (
                "confirmed structural break, majority momentum alignment, and closed evidence"
                if entry_confirmation_complete
                else (
                    "setup preserved but current-price execution remains conditional; "
                    "use a pullback, retest, reclaim, or renewed confirmation"
                )
            ),
            "decision_atr": atr,
            "invalidation_includes_noise_buffer": True,
            "invalidation_buffer_source": "strategy_structure_or_volatility_stop",
        },
        entry_opportunities=entry_opportunities,
        provisional=context.provisional,
    )


def _continuation_freshness(
    context: StrategyContext,
    *,
    direction: TradeDirection,
    current: float,
    target: float,
) -> ContinuationFreshness | None:
    candles = tuple(candle for candle in context.decision_frame.recent_candles if candle.is_closed)
    if len(candles) < 3:
        return None
    recent = candles[-12:]
    bullish = direction is TradeDirection.LONG
    impulse_origin = (
        min(candle.low for candle in recent) if bullish else max(candle.high for candle in recent)
    )
    if (bullish and impulse_origin >= current) or (not bullish and impulse_origin <= current):
        return None
    try:
        return measure_continuation_freshness(
            candles=recent,
            features=context.decision_frame.features,
            direction=direction,
            current_price=current,
            impulse_origin=impulse_origin,
            target_price=target,
        )
    except ValueError:
        return None


def _freshness_extension_penalty(
    freshness: ContinuationFreshness | None,
) -> float:
    if freshness is None:
        return 0.0
    if freshness.requires_conditional_entry:
        return 0.45
    return min(0.35, freshness.objective_consumption * 0.35)


def _freshness_metadata(
    freshness: ContinuationFreshness | None,
) -> dict[str, str | int | float | bool]:
    if freshness is None:
        return {"continuation_freshness_available": False}
    payload: dict[str, str | int | float | bool] = {
        "continuation_freshness_available": True,
        "continuation_state": freshness.state.value,
        "impulse_travel_atr": freshness.impulse_travel_atr,
        "objective_consumption": freshness.objective_consumption,
        "remaining_target_room_atr": freshness.remaining_target_room_atr,
        "momentum_decelerating": freshness.momentum_decelerating,
        "continuation_requires_conditional_entry": (freshness.requires_conditional_entry),
    }
    if freshness.ema_extension_atr is not None:
        payload["ema_extension_atr"] = freshness.ema_extension_atr
    if freshness.vwap_extension_atr is not None:
        payload["vwap_extension_atr"] = freshness.vwap_extension_atr
    return payload


def _participation_metadata(
    participation: ContinuationParticipation,
) -> dict[str, str | int | float | bool]:
    payload: dict[str, str | int | float | bool] = {
        "continuation_participation_state": participation.state.value,
        "participation_available_signal_count": participation.available_signal_count,
        "participation_supportive_signal_count": participation.supportive_signal_count,
        "participation_contradictory_signal_count": (participation.contradictory_signal_count),
    }
    if participation.relative_volume is not None:
        payload["relative_volume"] = participation.relative_volume
    if participation.open_interest_change is not None:
        payload["open_interest_change"] = participation.open_interest_change
    if participation.taker_buy_sell_ratio is not None:
        payload["taker_buy_sell_ratio"] = participation.taker_buy_sell_ratio
    return payload


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


def _invalidation_geometry(
    context: StrategyContext,
    *,
    bullish: bool,
) -> tuple[float, InvalidationType]:
    frame = context.decision_frame
    current = context.current_price
    role = LevelRole.SUPPORT if bullish else LevelRole.RESISTANCE
    levels = [
        item.representative_price
        for item in frame.structure.levels
        if item.role is role
        and item.status is not LevelStatus.BROKEN
        and (
            (bullish and item.representative_price < current)
            or (not bullish and item.representative_price > current)
        )
    ]
    if levels:
        anchor = max(levels) if bullish else min(levels)
        buffered = anchor - context.atr * 0.2 if bullish else anchor + context.atr * 0.2
        return buffered, InvalidationType.STRUCTURAL
    fallback = current - context.atr if bullish else current + context.atr
    return fallback, InvalidationType.VOLATILITY


def _target_geometry(
    context: StrategyContext,
    *,
    bullish: bool,
) -> tuple[float, TargetType, str]:
    frame = context.decision_frame
    current = context.current_price
    role = LevelRole.RESISTANCE if bullish else LevelRole.SUPPORT
    levels = [
        item.representative_price
        for item in frame.structure.levels
        if item.role is role
        and item.status is not LevelStatus.BROKEN
        and (
            (bullish and item.representative_price > current)
            or (not bullish and item.representative_price < current)
        )
    ]
    if levels:
        return (
            min(levels) if bullish else max(levels),
            TargetType.STRUCTURAL,
            "nearest observed opposing structural objective",
        )
    projected = current + context.atr * 2.2 if bullish else current - context.atr * 2.2
    return (
        projected,
        TargetType.EXPANSION,
        "2.2 ATR expansion projection; no verified opposing structure was available",
    )


def _volume_quality(value: float | None) -> float:
    return 0.5 if value is None else min(1.0, value / 2.0)


def _valid_geometry(*, current: float, invalidation: float, target: float, bullish: bool) -> bool:
    return invalidation < current < target if bullish else target < current < invalidation
