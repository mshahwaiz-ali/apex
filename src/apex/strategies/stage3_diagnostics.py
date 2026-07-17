"""Canonical Stage 3 strategy diagnostics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from apex.domain.futures import EntryState
from apex.strategies.context import StrategyContext, TimeframeRole
from apex.strategies.contracts import TradeCandidate, TradeDirection
from apex.strategies.strategy_types import StrategyType
from apex.structure.contracts import BreakDirection, ConfirmationStatus, TrendDirection
from apex.structure.regime import MarketRegime, classify_market_regime


class StrategyRejectionCode(StrEnum):
    TREND_MISMATCH = "trend_mismatch"
    MOMENTUM_MISMATCH = "momentum_mismatch"
    HIGHER_TIMEFRAME_CONTRADICTION = "higher_timeframe_contradiction"
    INVALID_STOP_TARGET_GEOMETRY = "invalid_stop_target_geometry"
    MISSING_ENTRY_REFERENCES = "missing_entry_references"
    EXCESSIVE_DISTANCE_FROM_CURRENT = "excessive_distance_from_current_price"
    NO_STRATEGY_TRIGGER = "no_strategy_trigger"


@dataclass(frozen=True, slots=True)
class StrategyDiagnostic:
    strategy: StrategyType
    candidate_count: int
    rejection_codes: tuple[StrategyRejectionCode, ...]
    reasons: tuple[str, ...]
    near_miss_state: EntryState
    higher_timeframe_breakout: bool = False


_BULLISH = {
    TrendDirection.STRONG_BULLISH,
    TrendDirection.BULLISH,
    TrendDirection.WEAK_BULLISH,
}
_BEARISH = {
    TrendDirection.STRONG_BEARISH,
    TrendDirection.BEARISH,
    TrendDirection.WEAK_BEARISH,
}
_HIGHER_ROLES = {
    TimeframeRole.LONG_TERM_MACRO,
    TimeframeRole.SWING,
    TimeframeRole.MACRO,
    TimeframeRole.INTERMEDIATE,
    TimeframeRole.INTRADAY,
}
_BREAKOUT_FAMILIES = {
    StrategyType.MOMENTUM_BREAKOUT,
    StrategyType.BREAKOUT_CONTINUATION,
    StrategyType.BREAKOUT_RETEST,
    StrategyType.COMPRESSION_EXPANSION,
}
_PULLBACK_FAMILIES = {
    StrategyType.FIRST_PULLBACK_CONTINUATION,
    StrategyType.TREND_PULLBACK,
}
_MAX_REFERENCE_DISTANCE_ATR = 3.0


def build_strategy_diagnostics(
    context: StrategyContext,
    *,
    evaluated: Sequence[StrategyType],
    eligible: Sequence[StrategyType],
    skipped: Mapping[StrategyType, str],
    candidates: Sequence[TradeCandidate],
) -> Mapping[StrategyType, StrategyDiagnostic]:
    """Explain generated candidates and unmet family-specific triggers."""

    del eligible, skipped
    higher_breakout = has_higher_timeframe_breakout(context)
    diagnostics: dict[StrategyType, StrategyDiagnostic] = {}
    for strategy in evaluated:
        produced = tuple(
            item for item in candidates if StrategyType(item.strategy.value) is strategy
        )
        if produced:
            diagnostics[strategy] = StrategyDiagnostic(
                strategy=strategy,
                candidate_count=len(produced),
                rejection_codes=(),
                reasons=("strategy generated at least one raw candidate",),
                near_miss_state=_best_state(tuple(_candidate_state(item) for item in produced)),
                higher_timeframe_breakout=higher_breakout,
            )
            continue
        codes, reasons = _infer_rejections(context, strategy)
        diagnostics[strategy] = StrategyDiagnostic(
            strategy=strategy,
            candidate_count=0,
            rejection_codes=codes,
            reasons=reasons,
            near_miss_state=_near_miss_state(context, strategy, codes),
            higher_timeframe_breakout=higher_breakout,
        )
    return MappingProxyType(diagnostics)


def has_higher_timeframe_breakout(context: StrategyContext) -> bool:
    """Return whether a higher timeframe has confirmed directional expansion."""

    for frame in context.frames:
        if frame is context.decision_frame or frame.role not in _HIGHER_ROLES:
            continue
        regime = classify_market_regime(frame.structure)
        confirmed = any(
            event.confirmation is ConfirmationStatus.CONFIRMED
            and event.direction in {BreakDirection.BULLISH, BreakDirection.BEARISH}
            for event in frame.structure.breaks
        )
        if regime is MarketRegime.BREAKOUT_EXPANSION or confirmed:
            return True
    return False


def _infer_rejections(
    context: StrategyContext,
    strategy: StrategyType,
) -> tuple[tuple[StrategyRejectionCode, ...], tuple[str, ...]]:
    frame = context.decision_frame
    codes: list[StrategyRejectionCode] = []
    reasons: list[str] = []
    bullish = _bullish_direction(frame.structure.trend.direction)
    momentum = tuple(
        value
        for value in (
            frame.features.rsi_slope,
            frame.features.macd_histogram,
            frame.features.rate_of_change,
        )
        if value is not None
    )
    if bullish is None:
        codes.append(StrategyRejectionCode.TREND_MISMATCH)
        reasons.append("decision-frame structure does not establish direction")
    else:
        if momentum and _momentum_mismatch(momentum, bullish=bullish):
            codes.append(StrategyRejectionCode.MOMENTUM_MISMATCH)
            reasons.append("decision-frame momentum contradicts the directional structure")
        if context.higher_timeframe_contradiction(bullish=bullish):
            codes.append(StrategyRejectionCode.HIGHER_TIMEFRAME_CONTRADICTION)
            reasons.append("higher-timeframe trend contradicts the decision thesis")

    if strategy in _BREAKOUT_FAMILIES:
        if not frame.structure.breaks and not has_higher_timeframe_breakout(context):
            codes.append(StrategyRejectionCode.MISSING_ENTRY_REFERENCES)
            reasons.append("no confirmed breakout or expansion reference exists")
    elif strategy in _PULLBACK_FAMILIES:
        features = frame.features
        if not frame.structure.levels and all(
            value is None for value in (features.ema_fast, features.ema_slow, features.vwap)
        ):
            codes.append(StrategyRejectionCode.MISSING_ENTRY_REFERENCES)
            reasons.append("no structural, EMA, or VWAP pullback reference exists")
    elif not frame.structure.levels:
        codes.append(StrategyRejectionCode.MISSING_ENTRY_REFERENCES)
        reasons.append("decision frame has no usable structural entry reference")

    if context.atr <= 0 or context.current_price <= 0:
        codes.append(StrategyRejectionCode.INVALID_STOP_TARGET_GEOMETRY)
        reasons.append("stop and target geometry cannot be constructed")
    elif _references_are_too_far(context):
        codes.append(StrategyRejectionCode.EXCESSIVE_DISTANCE_FROM_CURRENT)
        reasons.append("nearest structural reference is more than three ATR from current price")

    if not codes:
        codes.append(StrategyRejectionCode.NO_STRATEGY_TRIGGER)
        reasons.append("family-specific trigger conditions were not satisfied")
    return tuple(dict.fromkeys(codes)), tuple(dict.fromkeys(reasons))


def _bullish_direction(trend: TrendDirection) -> bool | None:
    if trend in _BULLISH:
        return True
    if trend in _BEARISH:
        return False
    return None


def _momentum_mismatch(values: Sequence[float], *, bullish: bool) -> bool:
    if bullish:
        return all(value <= 0 for value in values) and any(value < 0 for value in values)
    return all(value >= 0 for value in values) and any(value > 0 for value in values)


def _references_are_too_far(context: StrategyContext) -> bool:
    levels = context.decision_frame.structure.levels
    if not levels:
        return False
    nearest = min(
        abs(level.representative_price - context.current_price) for level in levels
    )
    return nearest > context.atr * _MAX_REFERENCE_DISTANCE_ATR


def _near_miss_state(
    context: StrategyContext,
    strategy: StrategyType,
    codes: Sequence[StrategyRejectionCode],
) -> EntryState:
    if StrategyRejectionCode.INVALID_STOP_TARGET_GEOMETRY in codes:
        return EntryState.INVALIDATED
    if StrategyRejectionCode.EXCESSIVE_DISTANCE_FROM_CURRENT in codes:
        return EntryState.MISSED_ENTRY
    if strategy in _BREAKOUT_FAMILIES and has_higher_timeframe_breakout(context):
        return EntryState.WAIT_FOR_RETEST
    if StrategyRejectionCode.MISSING_ENTRY_REFERENCES in codes:
        return EntryState.WATCH
    if StrategyRejectionCode.MOMENTUM_MISMATCH in codes:
        return EntryState.APPROACHING_ENTRY
    return EntryState.NO_TRADE


def _candidate_state(candidate: TradeCandidate) -> EntryState:
    current = candidate.entry.current_price
    if candidate.direction is TradeDirection.LONG:
        if current <= candidate.invalidation.price:
            return EntryState.INVALIDATED
        if candidate.entry.max_chase_price is not None and current > candidate.entry.max_chase_price:
            return EntryState.MISSED_ENTRY
    else:
        if current >= candidate.invalidation.price:
            return EntryState.INVALIDATED
        if candidate.entry.max_chase_price is not None and current < candidate.entry.max_chase_price:
            return EntryState.MISSED_ENTRY
    if candidate.entry.lower <= current <= candidate.entry.upper:
        return EntryState.READY_NOW
    if candidate.entry.mode.value == "retest":
        return EntryState.WAIT_FOR_RETEST
    return EntryState.APPROACHING_ENTRY


def _best_state(states: Sequence[EntryState]) -> EntryState:
    precedence = (
        EntryState.READY_NOW,
        EntryState.APPROACHING_ENTRY,
        EntryState.WAIT_FOR_RETEST,
        EntryState.WAIT_FOR_RECLAIM,
        EntryState.WATCH,
        EntryState.MISSED_ENTRY,
        EntryState.INVALIDATED,
        EntryState.NO_TRADE,
    )
    return min(states, key=precedence.index)
