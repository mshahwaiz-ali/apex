"""HTF-authorised conditional retest fallback for trend-pullback discovery."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apex.strategies.context import StrategyContext, TimeframeRole
from apex.strategies.contracts import (
    EntryMode,
    InvalidationConcept,
    RawQualityMetrics,
    StrategyEvidence,
    TargetConcept,
    TradeCandidate,
    TradeDirection,
)
from apex.strategies.entry import DEFAULT_ENTRY_SELECTION_CONFIG, find_entry_zones
from apex.strategies.strategy_types import StrategyType
from apex.strategies.target_ladder import (
    build_structural_target_ladder,
    fallback_expansion_target,
    target_ladder_metadata,
)
from apex.strategies.target_quality import target_space_quality
from apex.strategies.trend_pullback import (
    _BEARISH_TRENDS,
    _BULLISH_TRENDS,
    _entry_references,
    _invalidation_geometry,
    _momentum_quality,
    _optional_unit,
    _selected_entry_geometry_metadata,
    _valid_geometry,
    generate_trend_pullback_candidates,
)


def generate_htf_aware_trend_pullback_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    """Return normal pullbacks, or one conditional HTF-authorised retest fallback.

    The fallback is created only when setup and intraday parent frames agree,
    neither parent directly opposes the thesis, decision-frame structure remains
    aligned, and the ordinary generator failed because local momentum is not yet
    constructive. It never authorises immediate execution.
    """

    generated = generate_trend_pullback_candidates(
        context,
        decision_time=decision_time,
    )
    if generated:
        return generated

    fallbacks = tuple(
        candidate
        for direction in (TradeDirection.LONG, TradeDirection.SHORT)
        if (
            candidate := _fallback_for_direction(
                context,
                direction=direction,
                decision_time=decision_time,
            )
        )
        is not None
    )
    return tuple(sorted(fallbacks, key=lambda item: item.direction.value))


def _fallback_for_direction(
    context: StrategyContext,
    *,
    direction: TradeDirection,
    decision_time: datetime,
) -> TradeCandidate | None:
    bullish = direction is TradeDirection.LONG
    aligned_trends = _BULLISH_TRENDS if bullish else _BEARISH_TRENDS
    opposed_trends = _BEARISH_TRENDS if bullish else _BULLISH_TRENDS

    setup = context.frame_for_role(TimeframeRole.SETUP)
    intraday = context.frame_for_role(TimeframeRole.INTRADAY)
    frame = context.decision_frame

    if setup is None or intraday is None:
        return None
    if setup.structure.trend.direction not in aligned_trends:
        return None
    if intraday.structure.trend.direction not in aligned_trends:
        return None
    if any(
        parent.structure.trend.direction in opposed_trends
        for parent in (setup, intraday)
    ):
        return None
    if frame.structure.trend.direction not in aligned_trends:
        return None

    momentum_quality = _momentum_quality(context, bullish=bullish)
    if momentum_quality > 0.0:
        return None

    current = context.current_price
    atr = context.atr
    invalidation_price, invalidation_type = _invalidation_geometry(
        context,
        bullish=bullish,
    )
    target_levels = build_structural_target_ladder(context, direction=direction)
    if not target_levels:
        target_levels = (fallback_expansion_target(context, direction=direction),)
    primary_target = target_levels[0]
    if not _valid_geometry(
        current=current,
        invalidation=invalidation_price,
        target=primary_target.price,
        bullish=bullish,
    ):
        return None

    references = _entry_references(context, bullish=bullish)
    if not references:
        return None
    try:
        raw_entry_opportunities = find_entry_zones(
            current_price=current,
            atr=atr,
            direction=direction,
            invalidation_price=invalidation_price,
            target_price=primary_target.price,
            references=references,
            config=replace(
                DEFAULT_ENTRY_SELECTION_CONFIG,
                sweep_projection_enabled=True,
            ),
            allow_market_entry=False,
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
    if not raw_entry_opportunities:
        return None

    # This fallback exists specifically because local momentum is fully opposed.
    # Publish the selected zone as a retest, even when the shared selector formed
    # a scaled structural zone, so downstream execution requires acceptance/hold
    # confirmation rather than treating the first touch as a limit-entry trigger.
    entry = replace(raw_entry_opportunities[0], mode=EntryMode.RETEST)
    entry_opportunities = (entry, *raw_entry_opportunities[1:])
    geometry_metadata = _selected_entry_geometry_metadata(
        context,
        entry_lower=entry.lower,
        entry_upper=entry.upper,
        entry_preferred=entry.preferred,
        bullish=bullish,
    )
    features = frame.features
    parent_strength = min(
        setup.structure.trend.strength,
        intraday.structure.trend.strength,
    )
    warnings = (
        "decision-frame momentum is fully opposed; execution requires a fresh "
        "retest hold or reclaim",
        *(("active-candle evidence is provisional",) if context.provisional else ()),
    )

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
                "HTF trend-pullback thesis fails beyond the nearest structural support"
                if bullish
                else "HTF trend-pullback thesis fails beyond the nearest structural resistance",
            ),
        ),
        targets=TargetConcept(levels=target_levels),
        quality=RawQualityMetrics(
            trend_alignment=parent_strength,
            structure_quality=min(parent_strength, frame.structure.trend.strength),
            entry_quality=entry.location_quality,
            momentum_quality=0.0,
            volume_quality=_optional_unit(features.relative_volume, neutral=0.5),
            liquidity_quality=0.5,
            target_space_quality=target_space_quality(
                current=current,
                invalidation=invalidation_price,
                target=primary_target.price,
                target_type=primary_target.kind,
            ),
            extension_penalty=1.0 - entry.location_quality,
            conflict_penalty=0.0,
        ),
        evidence=StrategyEvidence(
            supporting=(
                f"{intraday.timeframe} and {setup.timeframe} parent structures agree",
                f"{frame.timeframe} structure remains aligned with the parent thesis",
                "local momentum mismatch is treated as pullback timing, not thesis failure",
                "entry is deferred to a predefined retest or reclaim zone",
            ),
            warnings=warnings,
            feature_references=tuple(
                name
                for name, value in (
                    ("ema_fast", features.ema_fast),
                    ("ema_slow", features.ema_slow),
                    ("vwap", features.vwap),
                    ("rsi_slope", features.rsi_slope),
                    ("macd_histogram", features.macd_histogram),
                    ("rate_of_change", features.rate_of_change),
                )
                if value is not None
            ),
            structure_references=("trend", "levels", "parent_timeframe_authority"),
        ),
        metadata={
            "decision_timeframe": frame.timeframe,
            "decision_atr": atr,
            "decision_atr_percentage": atr / current * 100.0,
            "reference_count": len(references),
            "higher_timeframe_conflict": False,
            "parent_direction_authority": True,
            "htf_retest_fallback": True,
            "entry_confirmation_complete": False,
            "entry_confirmation_reason": (
                "parent trend is established but local momentum is opposed; "
                "wait for retest hold or reclaim"
            ),
            "momentum_mismatch_treatment": "conditional_retest",
            "invalidation_includes_noise_buffer": True,
            "invalidation_buffer_source": "strategy_structure_or_volatility_stop",
            **target_ladder_metadata(target_levels),
            **geometry_metadata,
        },
        entry_opportunities=entry_opportunities,
        provisional=context.provisional,
    )


__all__ = ["generate_htf_aware_trend_pullback_candidates"]
