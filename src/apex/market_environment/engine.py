"""Deterministic per-timeframe regime classification and multi-timeframe fusion."""

from __future__ import annotations

from collections.abc import Sequence

from apex.market_environment.config import (
    DEFAULT_MARKET_ENVIRONMENT_CONFIG,
    MarketEnvironmentConfig,
)
from apex.market_environment.contracts import (
    ConflictState,
    ExtensionState,
    HigherTimeframeBias,
    InputCompleteness,
    MarketEnvironment,
    MarketRegime,
    TimeframeMarketSnapshot,
    TimeframeRegimeResult,
    VolatilityState,
)
from apex.strategies.context import StrategyContext, TimeframeContext
from apex.structure.contracts import (
    BreakDirection,
    BreakQuality,
    ConfirmationStatus,
    RangeBreakoutState,
    SwingType,
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
_BULLISH_REGIMES = {
    MarketRegime.TREND_UP,
    MarketRegime.BREAKOUT_EXPANSION_UP,
    MarketRegime.BREAKOUT_RETEST_UP,
    MarketRegime.REVERSAL_UP,
}
_BEARISH_REGIMES = {
    MarketRegime.TREND_DOWN,
    MarketRegime.BREAKOUT_EXPANSION_DOWN,
    MarketRegime.BREAKOUT_RETEST_DOWN,
    MarketRegime.REVERSAL_DOWN,
}


def snapshot_from_timeframe(frame: TimeframeContext) -> TimeframeMarketSnapshot:
    """Adapt canonical strategy context into a strict environment snapshot."""

    confirmed_highs = tuple(
        swing.price
        for swing in frame.structure.swings
        if swing.kind is SwingType.HIGH and swing.status.value == "confirmed"
    )
    confirmed_lows = tuple(
        swing.price
        for swing in frame.structure.swings
        if swing.kind is SwingType.LOW and swing.status.value == "confirmed"
    )
    latest_break = frame.structure.breaks[-1] if frame.structure.breaks else None
    latest_range = frame.structure.ranges[-1] if frame.structure.ranges else None
    missing: list[str] = []
    optional_values = {
        "ema_fast": frame.features.ema_fast,
        "ema_slow": frame.features.ema_slow,
        "vwap": frame.features.vwap,
        "rsi": frame.features.rsi,
        "macd_histogram": frame.features.macd_histogram,
        "relative_volume": frame.features.relative_volume,
        "range_position": frame.features.range_position,
        "volatility_expansion": frame.features.volatility_expansion,
    }
    missing.extend(name for name, value in optional_values.items() if value is None)
    missing.extend(("ema_slope", "candle_body_ratio", "wick_ratios", "volume"))
    return TimeframeMarketSnapshot(
        timeframe=frame.timeframe,
        candle_timestamp=frame.last_closed_at,
        current_price=frame.current_price,
        last_closed_price=frame.latest_closed_price,
        recent_swing_high=confirmed_highs[-1] if confirmed_highs else None,
        recent_swing_low=confirmed_lows[-1] if confirmed_lows else None,
        trend_direction=frame.structure.trend.direction.value,
        ema_fast=frame.features.ema_fast,
        ema_slow=frame.features.ema_slow,
        ema_slope=None,
        vwap=frame.features.vwap,
        atr=frame.features.atr,
        candle_body_ratio=None,
        upper_wick_ratio=None,
        lower_wick_ratio=None,
        volume=None,
        relative_volume=frame.features.relative_volume,
        rsi=frame.features.rsi,
        macd_histogram=frame.features.macd_histogram,
        recent_high_break=(
            latest_break.direction is BreakDirection.BULLISH
            if latest_break is not None
            else None
        ),
        recent_low_break=(
            latest_break.direction is BreakDirection.BEARISH
            if latest_break is not None
            else None
        ),
        consolidation=latest_range is not None,
        compression=(
            frame.features.volatility_expansion
            is not None
            and frame.features.volatility_expansion <= 0.75
        ),
        range_position=frame.features.range_position,
        volatility_expansion=frame.features.volatility_expansion,
        data_confidence=frame.data_confidence,
        missing_data=tuple(missing),
    )


def classify_timeframe_regime(
    snapshot: TimeframeMarketSnapshot,
    *,
    config: MarketEnvironmentConfig = DEFAULT_MARKET_ENVIRONMENT_CONFIG,
) -> TimeframeRegimeResult:
    """Classify one timeframe using stable precedence and explainable evidence."""

    trend = TrendDirection(snapshot.trend_direction)
    volatility = _volatility_state(snapshot, config)
    extension = _extension_state(snapshot, config)
    bullish_score, bearish_score = _direction_scores(snapshot, trend)
    codes: list[str] = []
    reasons: list[str] = []

    if snapshot.data_confidence < 0.5:
        regime = MarketRegime.UNTRADEABLE
        codes.append("LOW_DATA_CONFIDENCE")
        reasons.append("Timeframe data confidence is below the tradeable threshold")
    elif volatility is VolatilityState.EXTREME and trend in {
        TrendDirection.TRANSITION,
        TrendDirection.UNCERTAIN,
    }:
        regime = MarketRegime.NOISY
        codes.append("EXTREME_VOLATILITY_WITHOUT_STRUCTURE")
        reasons.append("Extreme volatility is not supported by directional structure")
    else:
        regime = _classify_structural_regime(snapshot, trend, volatility, extension, config)
        codes.extend(_regime_codes(regime))
        reasons.extend(_regime_reasons(regime))

    if extension in {ExtensionState.OVEREXTENDED, ExtensionState.EXTREME}:
        codes.append("TIMEFRAME_EXTENSION_WARNING")
        reasons.append("Price is materially extended from its recent mean")
    if volatility in {VolatilityState.EXPANDING, VolatilityState.EXTREME}:
        codes.append("TIMEFRAME_VOLATILITY_EXPANSION")
        reasons.append("Volatility is expanding on this timeframe")
    if snapshot.missing_data:
        codes.append("OPTIONAL_DATA_MISSING")
        reasons.append("Some optional timeframe features are unavailable")

    return TimeframeRegimeResult(
        snapshot=snapshot,
        regime=regime,
        volatility_state=volatility,
        extension_state=extension,
        bullish_score=round(bullish_score, 6),
        bearish_score=round(bearish_score, 6),
        reason_codes=tuple(dict.fromkeys(codes)),
        reasons=tuple(dict.fromkeys(reasons)),
    )


def build_market_environment(
    context: StrategyContext,
    *,
    config: MarketEnvironmentConfig = DEFAULT_MARKET_ENVIRONMENT_CONFIG,
) -> MarketEnvironment:
    """Fuse available timeframes into one deterministic trading environment."""

    results = {
        frame.timeframe: classify_timeframe_regime(snapshot_from_timeframe(frame), config=config)
        for frame in context.frames
        if frame.timeframe in config.required_timeframes
    }
    available = set(results)
    missing = tuple(timeframe for timeframe in config.required_timeframes if timeframe not in available)
    completeness = _completeness(len(results), len(missing), config)
    execution_timeframe = _select_timeframe(config.execution_priority, available, context)
    entry_timeframe = _select_timeframe(config.entry_priority, available, context)
    higher_bias = _higher_timeframe_bias(results, config)
    long_score, short_score = _suitability_scores(results, config)
    alignment_score = max(long_score, short_score)
    conflict_state, conflict_score = _conflict_state(results, higher_bias, config)
    primary_regime = _primary_regime(results, execution_timeframe, config)
    volatility = _aggregate_volatility(results, config)
    extension = _aggregate_extension(results, config)
    codes, reasons = _fusion_reasons(
        primary_regime,
        higher_bias,
        conflict_state,
        extension,
        volatility,
        completeness,
    )
    tradeable = (
        completeness is not InputCompleteness.INSUFFICIENT
        and primary_regime not in {MarketRegime.UNTRADEABLE, MarketRegime.UNKNOWN}
        and alignment_score >= config.minimum_tradeability_score
        and conflict_score <= config.maximum_tradeable_conflict_score
    )
    if not tradeable:
        codes.append("ENVIRONMENT_NOT_TRADEABLE")
        reasons.append("Environment does not meet configured tradeability thresholds")
    else:
        codes.append("ENVIRONMENT_TRADEABLE")
        reasons.append("Environment meets configured tradeability thresholds")

    return MarketEnvironment(
        primary_regime=primary_regime,
        higher_timeframe_bias=higher_bias,
        execution_timeframe=execution_timeframe,
        entry_timeframe=entry_timeframe,
        alignment_score=round(alignment_score, 6),
        conflict_score=round(conflict_score, 6),
        conflict_state=conflict_state,
        volatility_state=volatility,
        extension_state=extension,
        tradeable=tradeable,
        long_suitability_score=round(long_score, 6),
        short_suitability_score=round(short_score, 6),
        reason_codes=tuple(dict.fromkeys(codes)),
        reasons=tuple(dict.fromkeys(reasons)),
        missing_timeframes=missing,
        input_completeness=completeness,
        timeframe_regimes=results,
    )


def market_environment_payload(environment: MarketEnvironment) -> dict[str, object]:
    """Serialize the fused environment with stable ordering."""

    return {
        "primary_regime": environment.primary_regime.value,
        "higher_timeframe_bias": environment.higher_timeframe_bias.value,
        "execution_timeframe": environment.execution_timeframe,
        "entry_timeframe": environment.entry_timeframe,
        "alignment_score": environment.alignment_score,
        "conflict_score": environment.conflict_score,
        "conflict_state": environment.conflict_state.value,
        "volatility_state": environment.volatility_state.value,
        "extension_state": environment.extension_state.value,
        "tradeable": environment.tradeable,
        "long_suitability_score": environment.long_suitability_score,
        "short_suitability_score": environment.short_suitability_score,
        "missing_timeframes": list(environment.missing_timeframes),
        "input_completeness": environment.input_completeness.value,
        "reason_codes": list(environment.reason_codes),
        "reasons": list(environment.reasons),
        "timeframe_regimes": {
            timeframe: {
                "regime": result.regime.value,
                "volatility_state": result.volatility_state.value,
                "extension_state": result.extension_state.value,
                "bullish_score": result.bullish_score,
                "bearish_score": result.bearish_score,
                "reason_codes": list(result.reason_codes),
                "missing_data": list(result.snapshot.missing_data),
            }
            for timeframe, result in environment.timeframe_regimes.items()
        },
    }


def _classify_structural_regime(
    snapshot: TimeframeMarketSnapshot,
    trend: TrendDirection,
    volatility: VolatilityState,
    extension: ExtensionState,
    config: MarketEnvironmentConfig,
) -> MarketRegime:
    if snapshot.consolidation and volatility is VolatilityState.COMPRESSED:
        return MarketRegime.SQUEEZE
    if snapshot.recent_high_break:
        if snapshot.range_position is not None and snapshot.range_position < 0.8:
            return MarketRegime.FAILED_BREAKOUT_UP
        if extension in {ExtensionState.OVEREXTENDED, ExtensionState.EXTREME}:
            return MarketRegime.EXHAUSTION_UP
        if volatility in {VolatilityState.EXPANDING, VolatilityState.EXTREME}:
            return MarketRegime.BREAKOUT_EXPANSION_UP
        return MarketRegime.BREAKOUT_RETEST_UP
    if snapshot.recent_low_break:
        if snapshot.range_position is not None and snapshot.range_position > 0.2:
            return MarketRegime.FAILED_BREAKOUT_DOWN
        if extension in {ExtensionState.OVEREXTENDED, ExtensionState.EXTREME}:
            return MarketRegime.EXHAUSTION_DOWN
        if volatility in {VolatilityState.EXPANDING, VolatilityState.EXTREME}:
            return MarketRegime.BREAKOUT_EXPANSION_DOWN
        return MarketRegime.BREAKOUT_RETEST_DOWN
    if trend in _BULLISH_TRENDS:
        if snapshot.rsi is not None and snapshot.rsi >= 75 and extension is not ExtensionState.NORMAL:
            return MarketRegime.EXHAUSTION_UP
        return MarketRegime.TREND_UP
    if trend in _BEARISH_TRENDS:
        if snapshot.rsi is not None and snapshot.rsi <= 25 and extension is not ExtensionState.NORMAL:
            return MarketRegime.EXHAUSTION_DOWN
        return MarketRegime.TREND_DOWN
    if trend is TrendDirection.RANGE or snapshot.consolidation:
        return MarketRegime.RANGE
    if trend is TrendDirection.TRANSITION:
        if snapshot.macd_histogram is not None and snapshot.macd_histogram > 0:
            return MarketRegime.REVERSAL_UP
        if snapshot.macd_histogram is not None and snapshot.macd_histogram < 0:
            return MarketRegime.REVERSAL_DOWN
    return MarketRegime.UNKNOWN


def _direction_scores(
    snapshot: TimeframeMarketSnapshot,
    trend: TrendDirection,
) -> tuple[float, float]:
    bullish = 50.0
    bearish = 50.0
    if trend in _BULLISH_TRENDS:
        bullish += 25.0
        bearish -= 25.0
    elif trend in _BEARISH_TRENDS:
        bullish -= 25.0
        bearish += 25.0
    if snapshot.ema_ordering == "bullish":
        bullish += 10.0
        bearish -= 10.0
    elif snapshot.ema_ordering == "bearish":
        bullish -= 10.0
        bearish += 10.0
    if snapshot.macd_histogram is not None:
        if snapshot.macd_histogram > 0:
            bullish += 8.0
            bearish -= 8.0
        elif snapshot.macd_histogram < 0:
            bullish -= 8.0
            bearish += 8.0
    if snapshot.rsi is not None:
        if snapshot.rsi >= 55:
            bullish += 7.0
            bearish -= 7.0
        elif snapshot.rsi <= 45:
            bullish -= 7.0
            bearish += 7.0
    return max(0.0, min(100.0, bullish)), max(0.0, min(100.0, bearish))


def _volatility_state(
    snapshot: TimeframeMarketSnapshot,
    config: MarketEnvironmentConfig,
) -> VolatilityState:
    value = snapshot.volatility_expansion
    if value is None:
        return VolatilityState.UNKNOWN
    if value <= config.volatility_compressed_max:
        return VolatilityState.COMPRESSED
    if value >= config.volatility_extreme_min:
        return VolatilityState.EXTREME
    if value >= config.volatility_expanding_min:
        return VolatilityState.EXPANDING
    return VolatilityState.NORMAL


def _extension_state(
    snapshot: TimeframeMarketSnapshot,
    config: MarketEnvironmentConfig,
) -> ExtensionState:
    values = tuple(
        abs(value)
        for value in (snapshot.price_to_vwap_atr, snapshot.price_to_ema_mean_atr)
        if value is not None
    )
    if not values:
        return ExtensionState.UNKNOWN
    extension = max(values)
    if extension >= config.extension_extreme_atr:
        return ExtensionState.EXTREME
    if extension >= config.extension_overextended_atr:
        return ExtensionState.OVEREXTENDED
    if extension >= config.extension_moderate_atr:
        return ExtensionState.MODERATE
    if extension < 0.35:
        return ExtensionState.UNDEREXTENDED
    return ExtensionState.NORMAL


def _higher_timeframe_bias(
    results: dict[str, TimeframeRegimeResult],
    config: MarketEnvironmentConfig,
) -> HigherTimeframeBias:
    selected = [results[item] for item in config.higher_timeframes if item in results]
    if not selected:
        return HigherTimeframeBias.UNKNOWN
    bullish = sum(item.bullish_score for item in selected) / len(selected)
    bearish = sum(item.bearish_score for item in selected) / len(selected)
    if abs(bullish - bearish) < 10:
        return HigherTimeframeBias.CONFLICTED if len(selected) > 1 else HigherTimeframeBias.NEUTRAL
    if bullish >= 75:
        return HigherTimeframeBias.STRONGLY_BULLISH
    if bullish > bearish:
        return HigherTimeframeBias.BULLISH
    if bearish >= 75:
        return HigherTimeframeBias.STRONGLY_BEARISH
    return HigherTimeframeBias.BEARISH


def _suitability_scores(
    results: dict[str, TimeframeRegimeResult],
    config: MarketEnvironmentConfig,
) -> tuple[float, float]:
    available_weight = sum(config.timeframe_weights[item] for item in results)
    if available_weight <= 0:
        return 0.0, 0.0
    long_score = sum(
        result.bullish_score * config.timeframe_weights[timeframe]
        for timeframe, result in results.items()
    ) / available_weight
    short_score = sum(
        result.bearish_score * config.timeframe_weights[timeframe]
        for timeframe, result in results.items()
    ) / available_weight
    return long_score, short_score


def _conflict_state(
    results: dict[str, TimeframeRegimeResult],
    bias: HigherTimeframeBias,
    config: MarketEnvironmentConfig,
) -> tuple[ConflictState, float]:
    structure = [results[item] for item in config.structure_timeframes if item in results]
    if bias in {HigherTimeframeBias.BULLISH, HigherTimeframeBias.STRONGLY_BULLISH} and any(
        item.regime in _BEARISH_REGIMES for item in structure
    ):
        return ConflictState.STRUCTURAL_CONFLICT, 70.0
    if bias in {HigherTimeframeBias.BEARISH, HigherTimeframeBias.STRONGLY_BEARISH} and any(
        item.regime in _BULLISH_REGIMES for item in structure
    ):
        return ConflictState.STRUCTURAL_CONFLICT, 70.0
    lower = [results[item] for item in ("5m", "3m", "1m") if item in results]
    if bias in {HigherTimeframeBias.BULLISH, HigherTimeframeBias.STRONGLY_BULLISH} and any(
        item.regime in _BEARISH_REGIMES for item in lower
    ):
        return ConflictState.TIMING_CONFLICT, 35.0
    if bias in {HigherTimeframeBias.BEARISH, HigherTimeframeBias.STRONGLY_BEARISH} and any(
        item.regime in _BULLISH_REGIMES for item in lower
    ):
        return ConflictState.TIMING_CONFLICT, 35.0
    if any(
        item.extension_state in {ExtensionState.OVEREXTENDED, ExtensionState.EXTREME}
        for item in results.values()
        if item.snapshot.timeframe in config.higher_timeframes
    ):
        return ConflictState.EXTENSION_WARNING, 20.0
    if any(item.volatility_state is VolatilityState.EXTREME for item in results.values()):
        return ConflictState.VOLATILITY_WARNING, 25.0
    return ConflictState.NONE, 0.0


def _primary_regime(
    results: dict[str, TimeframeRegimeResult],
    execution_timeframe: str,
    config: MarketEnvironmentConfig,
) -> MarketRegime:
    for timeframe in (*config.structure_timeframes, execution_timeframe, *config.execution_priority):
        result = results.get(timeframe)
        if result is not None and result.regime is not MarketRegime.UNKNOWN:
            return result.regime
    return MarketRegime.UNKNOWN


def _aggregate_volatility(
    results: dict[str, TimeframeRegimeResult],
    config: MarketEnvironmentConfig,
) -> VolatilityState:
    order = (
        VolatilityState.EXTREME,
        VolatilityState.EXPANDING,
        VolatilityState.COMPRESSED,
        VolatilityState.NORMAL,
    )
    preferred = [results[item] for item in config.structure_timeframes if item in results]
    selected = preferred or list(results.values())
    for state in order:
        if any(item.volatility_state is state for item in selected):
            return state
    return VolatilityState.UNKNOWN


def _aggregate_extension(
    results: dict[str, TimeframeRegimeResult],
    config: MarketEnvironmentConfig,
) -> ExtensionState:
    order = (
        ExtensionState.EXTREME,
        ExtensionState.OVEREXTENDED,
        ExtensionState.MODERATE,
        ExtensionState.NORMAL,
        ExtensionState.UNDEREXTENDED,
    )
    selected = [results[item] for item in config.higher_timeframes if item in results]
    selected = selected or list(results.values())
    for state in order:
        if any(item.extension_state is state for item in selected):
            return state
    return ExtensionState.UNKNOWN


def _select_timeframe(
    priority: Sequence[str],
    available: set[str],
    context: StrategyContext,
) -> str:
    for timeframe in priority:
        if timeframe in available:
            return timeframe
    return context.decision_frame.timeframe


def _completeness(
    available_count: int,
    missing_count: int,
    config: MarketEnvironmentConfig,
) -> InputCompleteness:
    if available_count < config.minimum_required_timeframes:
        return InputCompleteness.INSUFFICIENT
    if missing_count == 0:
        return InputCompleteness.COMPLETE
    if missing_count <= config.maximum_missing_timeframes:
        return InputCompleteness.PARTIAL
    return InputCompleteness.INSUFFICIENT


def _regime_codes(regime: MarketRegime) -> tuple[str, ...]:
    return (f"TIMEFRAME_{regime.value}",)


def _regime_reasons(regime: MarketRegime) -> tuple[str, ...]:
    return (f"Timeframe classified as {regime.value.lower().replace('_', ' ')}",)


def _fusion_reasons(
    regime: MarketRegime,
    bias: HigherTimeframeBias,
    conflict: ConflictState,
    extension: ExtensionState,
    volatility: VolatilityState,
    completeness: InputCompleteness,
) -> tuple[list[str], list[str]]:
    codes = [
        f"PRIMARY_REGIME_{regime.value}",
        f"HIGHER_TIMEFRAME_BIAS_{bias.value}",
        f"INPUT_{completeness.value}",
    ]
    reasons = [
        f"Primary regime is {regime.value.lower().replace('_', ' ')}",
        f"Higher-timeframe bias is {bias.value.lower().replace('_', ' ')}",
    ]
    if conflict is not ConflictState.NONE:
        codes.append(conflict.value)
        reasons.append(f"Conflict state is {conflict.value.lower().replace('_', ' ')}")
    if extension in {ExtensionState.OVEREXTENDED, ExtensionState.EXTREME}:
        codes.append("HIGH_TIMEFRAME_EXTENSION_WARNING")
        reasons.append("Higher-timeframe extension reduces confidence without forcing rejection")
    if volatility in {VolatilityState.EXPANDING, VolatilityState.EXTREME}:
        codes.append("VOLATILITY_EXPANSION_PRESENT")
        reasons.append("Volatility expansion affects risk and execution constraints")
    return codes, reasons
