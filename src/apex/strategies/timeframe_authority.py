"""Deterministic timeframe authority for breakout continuation and retest routing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.strategies.context import StrategyContext, TimeframeContext, TimeframeRole
from apex.strategies.contracts import TradeCandidate, TradeDirection
from apex.structure.contracts import TrendDirection


class Alignment(StrEnum):
    """Directional relationship between one timeframe and a candidate."""

    ALIGNED = "aligned"
    NEUTRAL = "neutral"
    OPPOSED = "opposed"
    STRONGLY_OPPOSED = "strongly_opposed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class BreakoutDirectionAuthority:
    """Resolved 30m/15m/5m/3m authority contract for one candidate."""

    direction_authority: Alignment
    setup_alignment: Alignment
    execution_alignment: Alignment
    retest_accepted: bool
    retest_failed: bool
    refinement_opposed: bool
    conditional_only: bool
    routing_rejection_reason: str | None

    @property
    def allowed(self) -> bool:
        return self.routing_rejection_reason is None

    def metadata(self) -> dict[str, str | bool]:
        return {
            "direction_authority": self.direction_authority.value,
            "setup_alignment": self.setup_alignment.value,
            "execution_alignment": self.execution_alignment.value,
            "retest_accepted": self.retest_accepted,
            "retest_failed": self.retest_failed,
            "refinement_opposed": self.refinement_opposed,
            "timing_frame_used_for_direction": False,
            "routing_rejection_reason": self.routing_rejection_reason or "",
        }


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
_STRONG_BULLISH = {TrendDirection.STRONG_BULLISH, TrendDirection.BULLISH}
_STRONG_BEARISH = {TrendDirection.STRONG_BEARISH, TrendDirection.BEARISH}


def _alignment(frame: TimeframeContext | None, *, direction: TradeDirection) -> Alignment:
    if frame is None:
        return Alignment.UNAVAILABLE
    trend = frame.structure.trend.direction
    aligned = _BULLISH if direction is TradeDirection.LONG else _BEARISH
    opposed = _BEARISH if direction is TradeDirection.LONG else _BULLISH
    strongly_opposed = _STRONG_BEARISH if direction is TradeDirection.LONG else _STRONG_BULLISH
    if trend in aligned:
        return Alignment.ALIGNED
    if trend in strongly_opposed:
        return Alignment.STRONGLY_OPPOSED
    if trend in opposed:
        return Alignment.OPPOSED
    return Alignment.NEUTRAL


def _retest_state(
    frame: TimeframeContext | None,
    *,
    direction: TradeDirection,
    level: float,
) -> tuple[bool, bool, Alignment]:
    if frame is None:
        return False, False, Alignment.UNAVAILABLE
    closed = tuple(candle for candle in frame.recent_candles if candle.is_closed)
    if not closed:
        return False, False, _alignment(frame, direction=direction)
    latest = closed[-1]
    tolerance = frame.features.atr * 0.15
    touched = (
        latest.low <= level + tolerance
        if direction is TradeDirection.LONG
        else latest.high >= level - tolerance
    )
    accepted = touched and (
        latest.close >= level if direction is TradeDirection.LONG else latest.close <= level
    )
    failed = (
        latest.close < level - tolerance
        if direction is TradeDirection.LONG
        else latest.close > level + tolerance
    )
    return accepted, failed, _alignment(frame, direction=direction)


def resolve_breakout_direction_authority(
    context: StrategyContext,
    candidate: TradeCandidate,
) -> BreakoutDirectionAuthority:
    """Apply 30m direction, 15m setup, 5m execution, 3m refinement and 1m monitor roles."""

    direction = candidate.direction
    intraday = context.frame_for_role(TimeframeRole.INTRADAY)
    setup = context.frame_for_role(TimeframeRole.SETUP)
    execution = context.frame_for_role(TimeframeRole.ENTRY)
    refinement = context.frame_for_role(TimeframeRole.REFINEMENT)

    direction_authority = _alignment(intraday, direction=direction)
    setup_alignment = _alignment(setup, direction=direction)
    retest_accepted, retest_failed, execution_alignment = _retest_state(
        execution,
        direction=direction,
        level=candidate.entry.preferred,
    )
    refinement_alignment = _alignment(refinement, direction=direction)
    refinement_opposed = refinement_alignment in {
        Alignment.OPPOSED,
        Alignment.STRONGLY_OPPOSED,
    }
    conditional_only = refinement_alignment is Alignment.STRONGLY_OPPOSED

    rejection: str | None = None
    if direction_authority in {Alignment.OPPOSED, Alignment.STRONGLY_OPPOSED}:
        rejection = "30m_direction_authority_opposed"
    elif setup_alignment in {Alignment.OPPOSED, Alignment.STRONGLY_OPPOSED}:
        rejection = "15m_setup_authority_opposed"
    elif retest_failed:
        rejection = "5m_retest_failed"
    elif not retest_accepted:
        rejection = "5m_retest_not_accepted"

    return BreakoutDirectionAuthority(
        direction_authority=direction_authority,
        setup_alignment=setup_alignment,
        execution_alignment=execution_alignment,
        retest_accepted=retest_accepted,
        retest_failed=retest_failed,
        refinement_opposed=refinement_opposed,
        conditional_only=conditional_only,
        routing_rejection_reason=rejection,
    )
