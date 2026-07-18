"""Contextual candlestick evidence for the methodology pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.application.methodology_contracts import (
    EvidenceEffect,
    EvidenceFamily,
    EvidenceObservation,
)
from apex.domain.models import Candle
from apex.strategies.context import StrategyContext, TimeframeContext


class CandlePatternDirection(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class CandleCompletionState(StrEnum):
    COMPLETED = "completed"
    PROVISIONAL = "provisional"


@dataclass(frozen=True, slots=True)
class CandlestickEvidence:
    pattern_id: str
    pattern_direction: CandlePatternDirection
    completion_state: CandleCompletionState
    prior_move_requirement: str
    location_quality: float
    body_ratio: float
    upper_wick_ratio: float
    lower_wick_ratio: float
    relative_range: float
    close_location: float
    volume_context: str
    confirmation_level: float | None
    invalidation_level: float
    crypto_gap_adaptation: str
    context_note: str
    evidence_strength: float
    standalone_trade_approval: bool = False
    target_source: str = "none; candlestick evidence does not generate targets"


def detect_contextual_candlesticks(
    context: StrategyContext,
) -> tuple[CandlestickEvidence, ...]:
    """Detect source-backed candle evidence without approving trades."""

    detected: list[CandlestickEvidence] = []
    for frame in context.frames:
        detected.extend(_detect_frame(frame))
    return tuple(detected)


def candlestick_evidence_observations(
    patterns: tuple[CandlestickEvidence, ...],
) -> tuple[EvidenceObservation, ...]:
    """Convert candle detections to capped canonical evidence observations."""

    observations: list[EvidenceObservation] = []
    for pattern in patterns:
        effect = (
            EvidenceEffect.NEUTRAL
            if pattern.pattern_direction is CandlePatternDirection.NEUTRAL
            else EvidenceEffect.SUPPORTS
        )
        observations.append(
            EvidenceObservation(
                family=EvidenceFamily.CANDLE,
                source=f"candlestick:{pattern.pattern_id}",
                normalized_strength=pattern.evidence_strength,
                freshness=1.0
                if pattern.completion_state is CandleCompletionState.COMPLETED
                else 0.5,
                independence_group="candlestick_context",
                effect=effect,
                reason=(
                    f"{pattern.pattern_id} {pattern.pattern_direction.value} "
                    f"candle evidence; {pattern.context_note}"
                ),
            )
        )
    return tuple(observations)


def candlestick_evidence_payload(
    patterns: tuple[CandlestickEvidence, ...],
) -> list[dict[str, object]]:
    return [
        {
            "pattern_id": item.pattern_id,
            "pattern_direction": item.pattern_direction.value,
            "completion_state": item.completion_state.value,
            "prior_move_requirement": item.prior_move_requirement,
            "location_quality": item.location_quality,
            "body_ratio": item.body_ratio,
            "upper_wick_ratio": item.upper_wick_ratio,
            "lower_wick_ratio": item.lower_wick_ratio,
            "relative_range": item.relative_range,
            "close_location": item.close_location,
            "volume_context": item.volume_context,
            "confirmation_level": item.confirmation_level,
            "invalidation_level": item.invalidation_level,
            "crypto_gap_adaptation": item.crypto_gap_adaptation,
            "context_note": item.context_note,
            "evidence_strength": item.evidence_strength,
            "standalone_trade_approval": item.standalone_trade_approval,
            "target_source": item.target_source,
        }
        for item in patterns
    ]


def _detect_frame(frame: TimeframeContext) -> tuple[CandlestickEvidence, ...]:
    candles = frame.recent_candles
    if len(candles) < 4:
        return ()
    ordered = tuple(candles)
    history = tuple(candle for candle in ordered[:-1] if candle.is_closed)
    if len(history) < 3:
        return ()

    latest = ordered[-1]
    previous = history[-1]
    prior = history[-2]
    direction = _prior_move(history)
    relative_range = _relative_range(tuple((*history, latest)))
    volume_context = _volume_context(tuple((*history, latest)))
    location_quality = _location_quality(frame, latest)
    completion_state = (
        CandleCompletionState.PROVISIONAL
        if candles and not candles[-1].is_closed
        else CandleCompletionState.COMPLETED
    )
    detected: list[CandlestickEvidence] = []

    body_ratio, upper_wick_ratio, lower_wick_ratio, close_location = _anatomy(latest)
    bullish_context = direction < 0
    bearish_context = direction > 0
    support_context = location_quality >= 0.55 and _near_lower_location(frame)
    resistance_context = location_quality >= 0.55 and _near_upper_location(frame)

    if _is_hammer(latest) and bullish_context:
        detected.append(
            _pattern(
                "hammer",
                CandlePatternDirection.BULLISH,
                completion_state,
                "prior decline required",
                location_quality if support_context else location_quality * 0.65,
                body_ratio,
                upper_wick_ratio,
                lower_wick_ratio,
                relative_range,
                close_location,
                volume_context,
                latest.high,
                latest.low,
                "strict gaps are not required for hammer evidence in continuous crypto",
                "hammer is timing evidence at support, not a standalone long approval",
            )
        )
    if _is_hammer(latest) and bearish_context:
        detected.append(
            _pattern(
                "hanging_man",
                CandlePatternDirection.BEARISH,
                completion_state,
                "prior advance required",
                location_quality if resistance_context else location_quality * 0.65,
                body_ratio,
                upper_wick_ratio,
                lower_wick_ratio,
                relative_range,
                close_location,
                volume_context,
                latest.low,
                latest.high,
                "classical session-gap strengthening is unavailable unless a true gap exists",
                "hanging-man evidence is a reversal warning until bearish confirmation appears",
            )
        )

    engulfing = _engulfing(previous, latest)
    if engulfing is not None:
        detected.append(
            _pattern(
                "bullish_engulfing" if engulfing > 0 else "bearish_engulfing",
                CandlePatternDirection.BULLISH if engulfing > 0 else CandlePatternDirection.BEARISH,
                completion_state,
                "opposite prior move required",
                location_quality,
                body_ratio,
                upper_wick_ratio,
                lower_wick_ratio,
                relative_range,
                close_location,
                volume_context,
                latest.high if engulfing > 0 else latest.low,
                min(previous.low, latest.low) if engulfing > 0 else max(previous.high, latest.high),
                "body engulfing is preserved; true high-low gaps are not fabricated",
                "engulfing evidence strengthens compatible structure but does not bypass gates",
            )
        )

    penetration = _penetration(previous, latest)
    if penetration >= 0.5 and previous.close < previous.open and latest.close > latest.open:
        detected.append(
            _pattern(
                "piercing_rejection",
                CandlePatternDirection.BULLISH,
                completion_state,
                "prior decline required",
                location_quality,
                body_ratio,
                upper_wick_ratio,
                lower_wick_ratio,
                relative_range,
                close_location,
                volume_context,
                latest.high,
                latest.low,
                "crypto adaptation uses close penetration without requiring a session gap",
                "piercing evidence requires structural target and stop validation elsewhere",
            )
        )
    if penetration <= -0.5 and previous.close > previous.open and latest.close < latest.open:
        detected.append(
            _pattern(
                "dark_cloud_rejection",
                CandlePatternDirection.BEARISH,
                completion_state,
                "prior advance required",
                location_quality,
                body_ratio,
                upper_wick_ratio,
                lower_wick_ratio,
                relative_range,
                close_location,
                volume_context,
                latest.low,
                latest.high,
                "crypto adaptation uses failed push and deep close without requiring a session gap",
                "dark-cloud evidence is not a short unless the broader strategy agrees",
            )
        )

    star_direction = _star(prior, previous, latest)
    if star_direction is not None:
        detected.append(
            _pattern(
                "morning_star" if star_direction > 0 else "evening_star",
                CandlePatternDirection.BULLISH
                if star_direction > 0
                else CandlePatternDirection.BEARISH,
                completion_state,
                "three-candle reversal after a prior move",
                location_quality,
                body_ratio,
                upper_wick_ratio,
                lower_wick_ratio,
                relative_range,
                close_location,
                volume_context,
                latest.high if star_direction > 0 else latest.low,
                min(prior.low, previous.low, latest.low)
                if star_direction > 0
                else max(prior.high, previous.high, latest.high),
                "body separation is accepted; true abandoned-baby gaps are not inferred",
                "star patterns are completed only after the third candle closes",
            )
        )

    if _is_shooting_star(latest) and bearish_context:
        detected.append(
            _pattern(
                "shooting_star",
                CandlePatternDirection.BEARISH,
                completion_state,
                "prior advance required",
                location_quality if resistance_context else location_quality * 0.65,
                body_ratio,
                upper_wick_ratio,
                lower_wick_ratio,
                relative_range,
                close_location,
                volume_context,
                latest.low,
                latest.high,
                "body gap is optional in continuous crypto and must not be fabricated",
                "shooting-star evidence is primarily a long-exit or short-confirmation warning",
            )
        )
    if _is_shooting_star(latest) and bullish_context:
        detected.append(
            _pattern(
                "inverted_hammer",
                CandlePatternDirection.BULLISH,
                completion_state,
                "prior decline required",
                location_quality if support_context else location_quality * 0.65,
                body_ratio,
                upper_wick_ratio,
                lower_wick_ratio,
                relative_range,
                close_location,
                volume_context,
                latest.high,
                latest.low,
                "confirmation is required because the upper wick alone does not prove control",
                "inverted-hammer evidence remains provisional until bullish follow-through",
            )
        )

    if body_ratio <= 0.1:
        detected.append(
            _pattern(
                "doji_indecision",
                CandlePatternDirection.NEUTRAL,
                completion_state,
                "prior move determines whether it is a warning",
                location_quality,
                body_ratio,
                upper_wick_ratio,
                lower_wick_ratio,
                relative_range,
                close_location,
                volume_context,
                None,
                latest.low if direction <= 0 else latest.high,
                "doji evidence is treated as indecision, not automatic reversal",
                "doji evidence can reduce certainty or request confirmation",
            )
        )

    if _is_harami(previous, latest):
        detected.append(
            _pattern(
                "harami_warning",
                CandlePatternDirection.NEUTRAL,
                completion_state,
                "large prior body containing smaller body",
                location_quality,
                body_ratio,
                upper_wick_ratio,
                lower_wick_ratio,
                relative_range,
                close_location,
                volume_context,
                previous.high if direction > 0 else previous.low,
                previous.low if direction > 0 else previous.high,
                "harami is compression/deceleration evidence, not a target source",
                "harami requires break of the two-candle range or added evidence",
            )
        )

    if _is_tweezer(previous, latest):
        detected.append(
            _pattern(
                "tweezer_rejection",
                CandlePatternDirection.BEARISH if direction > 0 else CandlePatternDirection.BULLISH,
                completion_state,
                "two tests of a nearby extreme after a prior move",
                location_quality,
                body_ratio,
                upper_wick_ratio,
                lower_wick_ratio,
                relative_range,
                close_location,
                volume_context,
                latest.low if direction > 0 else latest.high,
                max(previous.high, latest.high) if direction > 0 else min(previous.low, latest.low),
                "tweezer evidence uses tolerance around highs/lows, not session gaps",
                "tweezer evidence confirms rejection only with compatible structure",
            )
        )

    if relative_range >= 1.25 and body_ratio >= 0.65:
        detected.append(
            _pattern(
                "strong_expansion_candle",
                CandlePatternDirection.BULLISH
                if latest.close > latest.open
                else CandlePatternDirection.BEARISH,
                completion_state,
                "large body relative to recent range",
                location_quality,
                body_ratio,
                upper_wick_ratio,
                lower_wick_ratio,
                relative_range,
                close_location,
                volume_context,
                latest.high if latest.close > latest.open else latest.low,
                latest.low if latest.close > latest.open else latest.high,
                "expansion candle is participation/timing evidence only",
                "large candles may indicate continuation or exhaustion depending on structure",
            )
        )

    return tuple(detected)


def _pattern(
    pattern_id: str,
    direction: CandlePatternDirection,
    completion_state: CandleCompletionState,
    prior: str,
    location_quality: float,
    body_ratio: float,
    upper_wick_ratio: float,
    lower_wick_ratio: float,
    relative_range: float,
    close_location: float,
    volume_context: str,
    confirmation_level: float | None,
    invalidation_level: float,
    crypto_gap_adaptation: str,
    context_note: str,
) -> CandlestickEvidence:
    strength = _clamp(
        0.3 + _clamp(location_quality, 0.0, 1.0) * 0.35 + min(relative_range, 2.0) * 0.1,
        0.15,
        0.85,
    )
    return CandlestickEvidence(
        pattern_id=pattern_id,
        pattern_direction=direction,
        completion_state=completion_state,
        prior_move_requirement=prior,
        location_quality=round(_clamp(location_quality, 0.0, 1.0), 4),
        body_ratio=round(body_ratio, 4),
        upper_wick_ratio=round(upper_wick_ratio, 4),
        lower_wick_ratio=round(lower_wick_ratio, 4),
        relative_range=round(relative_range, 4),
        close_location=round(close_location, 4),
        volume_context=volume_context,
        confirmation_level=confirmation_level,
        invalidation_level=invalidation_level,
        crypto_gap_adaptation=crypto_gap_adaptation,
        context_note=context_note,
        evidence_strength=round(strength, 4),
    )


def _anatomy(candle: Candle) -> tuple[float, float, float, float]:
    candle_range = candle.high - candle.low
    if candle_range <= 0:
        return 0.0, 0.0, 0.0, 0.5
    body = abs(candle.close - candle.open)
    upper = candle.high - max(candle.open, candle.close)
    lower = min(candle.open, candle.close) - candle.low
    close_location = (candle.close - candle.low) / candle_range
    return body / candle_range, upper / candle_range, lower / candle_range, close_location


def _prior_move(candles: tuple[Candle, ...]) -> float:
    lookback = candles[-6:] if len(candles) >= 6 else candles
    if len(lookback) < 2:
        return 0.0
    start = lookback[0].close
    if start <= 0:
        return 0.0
    return (lookback[-1].close - start) / start


def _relative_range(candles: tuple[Candle, ...]) -> float:
    latest_range = candles[-1].high - candles[-1].low
    previous = [candle.high - candle.low for candle in candles[-11:-1]]
    baseline = sum(previous) / len(previous) if previous else latest_range
    return latest_range / baseline if baseline > 0 else 1.0


def _volume_context(candles: tuple[Candle, ...]) -> str:
    previous = [candle.volume for candle in candles[-11:-1]]
    baseline = sum(previous) / len(previous) if previous else 0.0
    if baseline <= 0:
        return "volume baseline unavailable"
    ratio = candles[-1].volume / baseline
    if ratio >= 1.5:
        return "volume expansion supports participation"
    if ratio <= 0.75:
        return "volume contraction limits confirmation"
    return "volume near baseline"


def _location_quality(frame: TimeframeContext, latest: Candle) -> float:
    range_position = frame.features.range_position
    if range_position is not None:
        return _clamp(max(1.0 - range_position, range_position), 0.0, 1.0)
    high = max(candle.high for candle in frame.recent_candles[-20:] if candle.is_closed)
    low = min(candle.low for candle in frame.recent_candles[-20:] if candle.is_closed)
    if high <= low:
        return 0.0
    position = (latest.close - low) / (high - low)
    return _clamp(max(1.0 - position, position), 0.0, 1.0)


def _near_lower_location(frame: TimeframeContext) -> bool:
    return frame.features.range_position is not None and frame.features.range_position <= 0.45


def _near_upper_location(frame: TimeframeContext) -> bool:
    return frame.features.range_position is not None and frame.features.range_position >= 0.55


def _is_hammer(candle: Candle) -> bool:
    body, upper, lower, _close_location = _anatomy(candle)
    return body <= 0.35 and lower >= max(0.45, body * 2.0) and upper <= 0.25


def _is_shooting_star(candle: Candle) -> bool:
    body, upper, lower, _close_location = _anatomy(candle)
    return body <= 0.35 and upper >= max(0.45, body * 2.0) and lower <= 0.25


def _engulfing(previous: Candle, latest: Candle) -> int | None:
    previous_low = min(previous.open, previous.close)
    previous_high = max(previous.open, previous.close)
    latest_low = min(latest.open, latest.close)
    latest_high = max(latest.open, latest.close)
    if (
        previous.close < previous.open
        and latest.close > latest.open
        and latest_low <= previous_low
        and latest_high >= previous_high
    ):
        return 1
    if (
        previous.close > previous.open
        and latest.close < latest.open
        and latest_low <= previous_low
        and latest_high >= previous_high
    ):
        return -1
    return None


def _penetration(previous: Candle, latest: Candle) -> float:
    body = abs(previous.close - previous.open)
    if body <= 0:
        return 0.0
    midpoint = (previous.open + previous.close) / 2.0
    if previous.close < previous.open:
        return (latest.close - midpoint) / body
    return (midpoint - latest.close) / body


def _star(first: Candle, star: Candle, third: Candle) -> int | None:
    first_body, *_ = _anatomy(first)
    star_body, *_ = _anatomy(star)
    third_body, *_ = _anatomy(third)
    if first_body < 0.45 or star_body > 0.35 or third_body < 0.45:
        return None
    midpoint = (first.open + first.close) / 2.0
    if first.close < first.open and third.close > third.open and third.close > midpoint:
        return 1
    if first.close > first.open and third.close < third.open and third.close < midpoint:
        return -1
    return None


def _is_harami(previous: Candle, latest: Candle) -> bool:
    previous_low = min(previous.open, previous.close)
    previous_high = max(previous.open, previous.close)
    latest_low = min(latest.open, latest.close)
    latest_high = max(latest.open, latest.close)
    previous_body, *_ = _anatomy(previous)
    latest_body, *_ = _anatomy(latest)
    return (
        previous_body >= 0.55
        and latest_body <= 0.35
        and previous_low <= latest_low <= latest_high <= previous_high
    )


def _is_tweezer(previous: Candle, latest: Candle) -> bool:
    tolerance = max(previous.high - previous.low, latest.high - latest.low) * 0.08
    return (
        abs(previous.high - latest.high) <= tolerance or abs(previous.low - latest.low) <= tolerance
    )


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))


__all__ = [
    "CandleCompletionState",
    "CandlePatternDirection",
    "CandlestickEvidence",
    "candlestick_evidence_observations",
    "candlestick_evidence_payload",
    "detect_contextual_candlesticks",
]
