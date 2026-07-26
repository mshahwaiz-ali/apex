"""Regime stability, symbol archetypes and derivatives-aware early warnings."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from statistics import median
from typing import Any

from apex.domain.futures_evidence import MarketEvidenceBundle
from apex.strategies import StrategyContext


class CoinArchetype(StrEnum):
    MAJOR = "major"
    LIQUID_ALT = "liquid_alt"
    MOMENTUM_ALT = "momentum_alt"
    INSUFFICIENT_HISTORY = "insufficient_history"
    BENCHMARK_DECOUPLED = "benchmark_decoupled"


class EarlyWarningState(StrEnum):
    BREAKOUT_PREPARATION = "breakout_preparation"
    BREAKDOWN_PREPARATION = "breakdown_preparation"
    BULLISH_PARTICIPATION = "bullish_participation"
    BEARISH_PARTICIPATION = "bearish_participation"
    SHORT_COVERING = "short_covering"
    LONG_LIQUIDATION = "long_liquidation"
    CROWDED_LONG_FRAGILITY = "crowded_long_fragility"
    CROWDED_SHORT_FRAGILITY = "crowded_short_fragility"
    EXHAUSTION_REVERSAL_WATCH = "exhaustion_reversal_watch"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NEUTRAL = "neutral"


@dataclass(frozen=True, slots=True)
class RegimeAssessment:
    state: str
    probability: float
    persistence: float
    transition_watch: bool


@dataclass(frozen=True, slots=True)
class EarlyWarningAssessment:
    state: EarlyWarningState
    confidence: float
    direction: str | None
    evidence: tuple[str, ...]
    concerns: tuple[str, ...]
    metrics: tuple[tuple[str, float], ...]


@dataclass(frozen=True, slots=True)
class RegimeHysteresis:
    """Pure transition guard usable by live and chronological research paths."""

    enter_probability: float = 0.68
    exit_probability: float = 0.42

    def select(self, previous: str | None, candidate: str, probability: float) -> str:
        if previous is None:
            return candidate
        if candidate == previous:
            return previous
        return candidate if probability >= self.enter_probability else previous


def build_market_intelligence(
    context: StrategyContext,
    regimes: dict[str, str],
    *,
    benchmark_correlation: float | None = None,
    previous_regime: str | None = None,
) -> dict[str, Any]:
    archetype = classify_coin_archetype(context, benchmark_correlation=benchmark_correlation)
    regime = assess_regime(context, regimes)
    selected_regime = RegimeHysteresis().select(
        previous_regime,
        regime.state,
        regime.probability,
    )
    warning = assess_early_warning(context, context.market_evidence)
    return {
        "archetype": archetype.value,
        "regime": {
            "state": selected_regime,
            "raw_state": regime.state,
            "probability": regime.probability,
            "persistence": regime.persistence,
            "transition_watch": regime.transition_watch,
            "previous_state": previous_regime,
            "hysteresis_applied": selected_regime != regime.state,
        },
        "early_warning": {
            "state": warning.state.value,
            "confidence": warning.confidence,
            "direction": warning.direction,
            "evidence": list(warning.evidence),
            "concerns": list(warning.concerns),
            "metrics": dict(warning.metrics),
        },
        "futures_evidence": evidence_bundle_payload(context.market_evidence),
    }


def classify_coin_archetype(
    context: StrategyContext, *, benchmark_correlation: float | None = None
) -> CoinArchetype:
    decision = context.decision_frame
    closed = tuple(candle for candle in decision.recent_candles if candle.is_closed)
    if len(closed) < 100:
        return CoinArchetype.INSUFFICIENT_HISTORY
    if benchmark_correlation is not None and abs(benchmark_correlation) < 0.20:
        return CoinArchetype.BENCHMARK_DECOUPLED
    lookback = closed[-min(24, len(closed)) :]
    quote_volumes = tuple(
        candle.quote_volume
        for candle in lookback
        if candle.quote_volume is not None and math.isfinite(candle.quote_volume)
    )
    if quote_volumes and median(quote_volumes) >= 100_000_000.0:
        return CoinArchetype.MAJOR
    move = abs(lookback[-1].close / lookback[0].open - 1.0)
    relative_volume = decision.features.relative_volume or 0.0
    if move >= 0.06 or relative_volume >= 1.8:
        return CoinArchetype.MOMENTUM_ALT
    return CoinArchetype.LIQUID_ALT


def assess_regime(context: StrategyContext, regimes: dict[str, str]) -> RegimeAssessment:
    states = tuple(regimes.get(frame.timeframe, "unknown") for frame in context.frames)
    winner = max(set(states), key=lambda state: (states.count(state), state))
    agreement = states.count(winner) / len(states)
    strengths = tuple(
        frame.features.trend_strength
        for frame in context.frames
        if frame.features.trend_strength is not None
    )
    strength = sum(strengths) / len(strengths) if strengths else 0.5
    probability = _clip(0.55 * agreement + 0.45 * strength)

    frame = context.decision_frame
    closed = tuple(candle for candle in frame.recent_candles if candle.is_closed)[-8:]
    if len(closed) >= 2:
        signs = tuple(1 if candle.close >= candle.open else -1 for candle in closed)
        persistence = max(signs.count(1), signs.count(-1)) / len(signs)
    else:
        persistence = agreement
    return RegimeAssessment(
        state=winner,
        probability=round(probability, 4),
        persistence=round(persistence, 4),
        transition_watch=probability < 0.58 or agreement < 0.60,
    )


def assess_early_warning(
    context: StrategyContext, bundle: MarketEvidenceBundle | None
) -> EarlyWarningAssessment:
    frame = context.decision_frame
    closed = tuple(candle for candle in frame.recent_candles if candle.is_closed)
    if len(closed) < 3 or bundle is None:
        return _warning(
            EarlyWarningState.INSUFFICIENT_EVIDENCE,
            concerns=("price history or derivatives evidence unavailable",),
        )

    price_change = closed[-1].close / closed[-3].close - 1.0
    range_position = frame.features.range_position
    compression = (frame.features.volatility_expansion or 1.0) < 0.80
    oi_change, oi_acceleration = _oi_metrics(bundle)
    taker_ratio = _taker_ratio(bundle)
    funding = bundle.funding[-1].funding_rate if bundle.funding else None
    basis = bundle.premium_index.basis_percentage if bundle.premium_index else None
    metrics = tuple(
        (name, value)
        for name, value in (
            ("price_change", price_change),
            ("oi_change", oi_change),
            ("oi_acceleration", oi_acceleration),
            ("taker_buy_sell_ratio", taker_ratio),
            ("funding_rate", funding),
            ("basis_percentage", basis),
        )
        if value is not None and math.isfinite(value)
    )
    concerns = tuple(f"{name}: {reason}" for name, reason in bundle.missing_reasons)

    # Price establishes direction. OI/flow only classify participation behind that move.
    if oi_change is not None and taker_ratio is not None:
        bullish_flow = taker_ratio >= 1.08
        bearish_flow = taker_ratio <= 0.92
        if price_change > 0.002 and oi_change > 0.002 and bullish_flow:
            return _warning(
                EarlyWarningState.BULLISH_PARTICIPATION,
                0.80,
                "long",
                ("price, OI and aggressive buying expand together",),
                concerns,
                metrics,
            )
        if price_change < -0.002 and oi_change > 0.002 and bearish_flow:
            return _warning(
                EarlyWarningState.BEARISH_PARTICIPATION,
                0.80,
                "short",
                ("price falls while OI and aggressive selling expand",),
                concerns,
                metrics,
            )
        if price_change > 0.002 and oi_change < -0.002:
            return _warning(
                EarlyWarningState.SHORT_COVERING,
                0.68,
                "long",
                ("price rises while OI contracts",),
                concerns,
                metrics,
            )
        if price_change < -0.002 and oi_change < -0.002:
            return _warning(
                EarlyWarningState.LONG_LIQUIDATION,
                0.68,
                "short",
                ("price falls while OI contracts",),
                concerns,
                metrics,
            )
        if (price_change > 0 and bearish_flow) or (price_change < 0 and bullish_flow):
            return _warning(
                EarlyWarningState.CONTRADICTORY_EVIDENCE,
                0.55,
                None,
                ("price and aggressive flow disagree",),
                concerns,
                metrics,
            )

    if compression and range_position is not None and taker_ratio is not None:
        if range_position >= 0.72 and taker_ratio >= 1.05:
            return _warning(
                EarlyWarningState.BREAKOUT_PREPARATION,
                0.64,
                "long",
                ("compression holds near range high with buy participation",),
                concerns,
                metrics,
            )
        if range_position <= 0.28 and taker_ratio <= 0.95:
            return _warning(
                EarlyWarningState.BREAKDOWN_PREPARATION,
                0.64,
                "short",
                ("compression holds near range low with sell participation",),
                concerns,
                metrics,
            )

    if funding is not None and abs(funding) >= 0.0005:
        state = (
            EarlyWarningState.CROWDED_LONG_FRAGILITY
            if funding > 0
            else EarlyWarningState.CROWDED_SHORT_FRAGILITY
        )
        return _warning(
            state,
            0.58,
            None,
            ("extreme funding indicates crowded positioning, not direction",),
            concerns,
            metrics,
        )
    if abs(price_change) >= 0.03 and oi_acceleration is not None and oi_acceleration < 0:
        return _warning(
            EarlyWarningState.EXHAUSTION_REVERSAL_WATCH,
            0.58,
            None,
            ("extended price move is losing OI acceleration",),
            concerns,
            metrics,
        )
    if len(bundle.available_inputs) < 2:
        return _warning(
            EarlyWarningState.INSUFFICIENT_EVIDENCE,
            concerns=concerns or ("fewer than two independent derivatives inputs",),
            metrics=metrics,
        )
    return _warning(
        EarlyWarningState.NEUTRAL,
        0.50,
        None,
        ("no coherent early-warning matrix is active",),
        concerns,
        metrics,
    )


def evidence_bundle_payload(bundle: MarketEvidenceBundle | None) -> dict[str, Any]:
    if bundle is None:
        return {"available": False, "missing_reasons": {"bundle": "disabled"}}
    return {
        "available": bool(bundle.available_inputs),
        "as_of": bundle.as_of.isoformat(),
        "source": bundle.source,
        "available_inputs": list(bundle.available_inputs),
        "execution_inputs": list(bundle.execution_inputs),
        "missing_reasons": dict(bundle.missing_reasons),
        "funding_observations": len(bundle.funding),
        "open_interest_observations": len(bundle.open_interest),
        "taker_flow_observations": len(bundle.taker_flow),
        "mark_price": bundle.premium_index.mark_price if bundle.premium_index else None,
        "index_price": bundle.premium_index.index_price if bundle.premium_index else None,
        "basis_percentage": bundle.premium_index.basis_percentage if bundle.premium_index else None,
        "spread_percentage": bundle.ticker.spread_percentage if bundle.ticker else None,
        "order_book_spread_percentage": (
            bundle.order_book.spread_percentage if bundle.order_book else None
        ),
        "order_book_depth_notional": (
            bundle.order_book.bid_depth_notional + bundle.order_book.ask_depth_notional
            if bundle.order_book
            else None
        ),
        "tick_size": bundle.exchange_filters.tick_size if bundle.exchange_filters else None,
        "step_size": bundle.exchange_filters.step_size if bundle.exchange_filters else None,
        "min_notional": (bundle.exchange_filters.min_notional if bundle.exchange_filters else None),
    }


def _oi_metrics(bundle: MarketEvidenceBundle) -> tuple[float | None, float | None]:
    values = bundle.open_interest
    if len(values) < 2 or values[-2].open_interest_value <= 0:
        return None, None
    latest_change = values[-1].open_interest_value / values[-2].open_interest_value - 1.0
    if len(values) < 3 or values[-3].open_interest_value <= 0:
        return latest_change, None
    previous_change = values[-2].open_interest_value / values[-3].open_interest_value - 1.0
    return latest_change, latest_change - previous_change


def _taker_ratio(bundle: MarketEvidenceBundle) -> float | None:
    recent = bundle.taker_flow[-3:]
    if not recent:
        return None
    sells = sum(item.sell_volume for item in recent)
    return sum(item.buy_volume for item in recent) / sells if sells > 0 else None


def _warning(
    state: EarlyWarningState,
    confidence: float = 0.0,
    direction: str | None = None,
    evidence: tuple[str, ...] = (),
    concerns: tuple[str, ...] = (),
    metrics: tuple[tuple[str, float], ...] = (),
) -> EarlyWarningAssessment:
    return EarlyWarningAssessment(
        state, round(_clip(confidence), 4), direction, evidence, concerns, metrics
    )


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


__all__ = [
    "CoinArchetype",
    "EarlyWarningAssessment",
    "EarlyWarningState",
    "RegimeAssessment",
    "RegimeHysteresis",
    "assess_early_warning",
    "assess_regime",
    "build_market_intelligence",
    "classify_coin_archetype",
]
