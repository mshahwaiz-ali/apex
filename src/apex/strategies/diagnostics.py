"""Deterministic Phase 4 rejection and near-miss diagnostics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from apex.domain.futures import EntryState
from apex.strategies.context import StrategyContext, TimeframeRole
from apex.strategies.contracts import StrategyType, TradeCandidate, TradeDirection
from apex.structure.contracts import BreakDirection, ConfirmationStatus, TrendDirection
from apex.structure.regime import MarketRegime, classify_market_regime


class Phase4RejectionCode(StrEnum):
    TREND_MISMATCH = "trend_mismatch"
    MOMENTUM_MISMATCH = "momentum_mismatch"
    HIGHER_TIMEFRAME_CONTRADICTION = "higher_timeframe_contradiction"
    INVALID_STOP_TARGET_GEOMETRY = "invalid_stop_target_geometry"
    MISSING_ENTRY_REFERENCES = "missing_entry_references"
    EXCESSIVE_DISTANCE_FROM_CURRENT = "excessive_distance_from_current_price"
    REGIME_INELIGIBLE = "regime_ineligible"
    NO_STRATEGY_TRIGGER = "no_strategy_trigger"


@dataclass(frozen=True, slots=True)
class StrategyDiagnostic:
    strategy: StrategyType
    candidate_count: int
    rejection_codes: tuple[Phase4RejectionCode, ...]
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


def build_phase4_diagnostics(
    context: StrategyContext,
    *,
    evaluated: Sequence[StrategyType],
    eligible: Sequence[StrategyType],
    skipped: Mapping[StrategyType, str],
    candidates: Sequence[TradeCandidate],
) -> Mapping[StrategyType, StrategyDiagnostic]:
    """Explain why each strategy generated candidates or remained a near miss."""

    diagnostics: dict[StrategyType, StrategyDiagnostic] = {}
    for strategy in evaluated:
        produced = tuple(item for item in candidates if item.strategy is strategy)
        if produced:
            states = tuple(_candidate_state(item) for item in produced)
            diagnostics[strategy] = StrategyDiagnostic(
                strategy=strategy,
                candidate_count=len(produced),
                rejection_codes=(),
                reasons=("strategy generated at least one raw candidate",),
                near_miss_state=_best_state(states),
                higher_timeframe_breakout=_has_higher_timeframe_breakout(context),
            )
            continue

        if strategy not in eligible:
            diagnostics[strategy] = StrategyDiagnostic(
                strategy=strategy,
                candidate_count=0,
                rejection_codes=(Phase4RejectionCode.REGIME_INELIGIBLE,),
                reasons=(skipped.get(strategy, "strategy is not eligible for the decision regime"),),
                near_miss_state=EntryState.NO_TRADE,
                higher_timeframe_breakout=_has_higher_timeframe_breakout(context),
            )
            continue

        codes, reasons = _infer_rejections(context, strategy)
        diagnostics[strategy] = StrategyDiagnostic(
            strategy=strategy,
            candidate_count=0,
            rejection_codes=codes,
            reasons=reasons,
            near_miss_state=_near_miss_state(context, strategy, codes),
            higher_timeframe_breakout=_has_higher_timeframe_breakout(context),
        )
    return MappingProxyType(diagnostics)


def has_higher_timeframe_breakout(context: StrategyContext) -> bool:
    """Return whether a higher/context timeframe has a confirmed directional break."""

    return _has_higher_timeframe_breakout(context)


def _infer_rejections(
    context: StrategyContext,
    strategy: StrategyType,
) -> tuple[tuple[Phase4RejectionCode, ...], tuple[str, ...]]:
    frame = context.decision_frame
    codes: list[Phase4RejectionCode] = []
    reasons: list[str] = []
    trend = frame.structure.trend.direction
    directional_momentum = tuple(
        value
        for value in (
            frame.features.rsi_slope,
            frame.features.macd_histogram,
            frame.features.rate_of_change,
        )
        if value is not None
    )

    if trend not in _BULLISH | _BEARISH:
        codes.append(Phase4RejectionCode.TREND_MISMATCH)
        reasons.append(f"decision-frame trend {trend.value} does not establish direction")
    if directional_momentum and not (
        any(value >= 0 for value in directional_momentum)
        or any(value <= 0 for value in directional_momentum)
    ):
        codes.append(Phase4RejectionCode.MOMENTUM_MISMATCH)
        reasons.append("decision-frame momentum does not support either direction")

    if strategy is StrategyType.BREAKOUT_CONTINUATION:
        if not frame.structure.breaks and not _has_higher_timeframe_breakout(context):
            codes.append(Phase4RejectionCode.MISSING_ENTRY_REFERENCES)
            reasons.append("no confirmed decision- or higher-timeframe breakout reference exists")
        elif _has_higher_timeframe_breakout(context) and not frame.structure.breaks:
            codes.append(Phase4RejectionCode.MISSING_ENTRY_REFERENCES)
            reasons.append("higher-timeframe breakout exists but lower-timeframe retest/reclaim is pending")
    elif not frame.structure.levels:
        codes.append(Phase4RejectionCode.MISSING_ENTRY_REFERENCES)
        reasons.append("decision frame has no usable structural entry references")

    if context.atr <= 0 or context.current_price <= 0:
        codes.append(Phase4RejectionCode.INVALID_STOP_TARGET_GEOMETRY)
        reasons.append("stop and target geometry cannot be constructed")

    if not codes:
        codes.append(Phase4RejectionCode.NO_STRATEGY_TRIGGER)
        reasons.append("strategy-specific trigger conditions were not satisfied")
    return tuple(dict.fromkeys(codes)), tuple(dict.fromkeys(reasons))


def _near_miss_state(
    context: StrategyContext,
    strategy: StrategyType,
    codes: Sequence[Phase4RejectionCode],
) -> EntryState:
    if Phase4RejectionCode.INVALID_STOP_TARGET_GEOMETRY in codes:
        return EntryState.INVALIDATED
    if Phase4RejectionCode.EXCESSIVE_DISTANCE_FROM_CURRENT in codes:
        return EntryState.MISSED_ENTRY
    if strategy is StrategyType.BREAKOUT_CONTINUATION and _has_higher_timeframe_breakout(context):
        frame = context.decision_frame
        trend = frame.structure.trend.direction
        if trend in _BULLISH | _BEARISH:
            return EntryState.WAIT_FOR_RETEST
        return EntryState.WAIT_FOR_RECLAIM
    if Phase4RejectionCode.MISSING_ENTRY_REFERENCES in codes:
        return EntryState.WATCH
    if Phase4RejectionCode.MOMENTUM_MISMATCH in codes:
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


def _has_higher_timeframe_breakout(context: StrategyContext) -> bool:
    for frame in context.frames:
        if frame.role not in _HIGHER_ROLES or frame is context.decision_frame:
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
