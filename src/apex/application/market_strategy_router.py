"""Environment-aware strategy eligibility and ranking."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.market_environment import (
    ConflictState,
    ExtensionState,
    HigherTimeframeBias,
    MarketEnvironment,
    MarketRegime,
    VolatilityState,
)
from apex.strategies import StrategyType, TradeDirection


class PreferredDirection(StrEnum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class MarketStrategyRoute:
    """Explainable environment-level strategy route."""

    allowed_strategies: tuple[StrategyType, ...]
    blocked_strategies: tuple[StrategyType, ...]
    preferred_direction: PreferredDirection
    strategy_priority: tuple[StrategyType, ...]
    routing_score: float
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]


_REGIME_STRATEGIES: dict[MarketRegime, tuple[StrategyType, ...]] = {
    MarketRegime.TREND_UP: (
        StrategyType.TREND_PULLBACK,
        StrategyType.FIRST_PULLBACK_CONTINUATION,
        StrategyType.MOMENTUM_BREAKOUT,
        StrategyType.BREAKOUT_CONTINUATION,
    ),
    MarketRegime.TREND_DOWN: (
        StrategyType.TREND_PULLBACK,
        StrategyType.FIRST_PULLBACK_CONTINUATION,
        StrategyType.MOMENTUM_BREAKOUT,
        StrategyType.BREAKOUT_CONTINUATION,
    ),
    MarketRegime.BREAKOUT_EXPANSION_UP: (
        StrategyType.BREAKOUT_CONTINUATION,
        StrategyType.MOMENTUM_BREAKOUT,
        StrategyType.MOMENTUM_SCALP,
        StrategyType.TREND_PULLBACK,
    ),
    MarketRegime.BREAKOUT_EXPANSION_DOWN: (
        StrategyType.BREAKOUT_CONTINUATION,
        StrategyType.MOMENTUM_BREAKOUT,
        StrategyType.MOMENTUM_SCALP,
        StrategyType.TREND_PULLBACK,
    ),
    MarketRegime.BREAKOUT_RETEST_UP: (
        StrategyType.BREAKOUT_CONTINUATION,
        StrategyType.TREND_PULLBACK,
        StrategyType.BREAKOUT_RETEST,
        StrategyType.FIRST_PULLBACK_CONTINUATION,
    ),
    MarketRegime.BREAKOUT_RETEST_DOWN: (
        StrategyType.BREAKOUT_CONTINUATION,
        StrategyType.TREND_PULLBACK,
        StrategyType.BREAKOUT_RETEST,
        StrategyType.FIRST_PULLBACK_CONTINUATION,
    ),
    MarketRegime.RANGE: (
        StrategyType.RANGE_REVERSAL,
        StrategyType.LIQUIDITY_REJECTION_REVERSAL,
    ),
    MarketRegime.FAILED_BREAKOUT_UP: (
        StrategyType.LIQUIDITY_REJECTION_REVERSAL,
        StrategyType.FAILED_BREAKOUT_REVERSAL,
        StrategyType.RANGE_REVERSAL,
        StrategyType.TREND_PULLBACK,
    ),
    MarketRegime.FAILED_BREAKOUT_DOWN: (
        StrategyType.LIQUIDITY_REJECTION_REVERSAL,
        StrategyType.FAILED_BREAKOUT_REVERSAL,
        StrategyType.RANGE_REVERSAL,
        StrategyType.TREND_PULLBACK,
    ),
    MarketRegime.EXHAUSTION_UP: (
        StrategyType.LIQUIDITY_REJECTION_REVERSAL,
        StrategyType.EXHAUSTION_REVERSAL,
        StrategyType.RANGE_REVERSAL,
        StrategyType.TREND_PULLBACK,
    ),
    MarketRegime.EXHAUSTION_DOWN: (
        StrategyType.LIQUIDITY_REJECTION_REVERSAL,
        StrategyType.EXHAUSTION_REVERSAL,
        StrategyType.RANGE_REVERSAL,
        StrategyType.TREND_PULLBACK,
    ),
    MarketRegime.REVERSAL_UP: (
        StrategyType.LIQUIDITY_REJECTION_REVERSAL,
        StrategyType.VWAP_RECLAIM_REJECTION,
        StrategyType.TREND_PULLBACK,
    ),
    MarketRegime.REVERSAL_DOWN: (
        StrategyType.LIQUIDITY_REJECTION_REVERSAL,
        StrategyType.VWAP_RECLAIM_REJECTION,
        StrategyType.TREND_PULLBACK,
    ),
    MarketRegime.SQUEEZE: (
        StrategyType.COMPRESSION_EXPANSION,
        StrategyType.BREAKOUT_CONTINUATION,
        StrategyType.MOMENTUM_BREAKOUT,
    ),
}


def route_market_strategies(environment: MarketEnvironment) -> MarketStrategyRoute:
    """Route strategies from fused regime, direction, conflict, and extension."""

    all_strategies = tuple(StrategyType)
    reasons: list[str] = []
    codes: list[str] = []
    if not environment.tradeable or environment.primary_regime in {
        MarketRegime.UNTRADEABLE,
        MarketRegime.UNKNOWN,
        MarketRegime.NOISY,
    }:
        return MarketStrategyRoute(
            allowed_strategies=(),
            blocked_strategies=all_strategies,
            preferred_direction=PreferredDirection.NONE,
            strategy_priority=(),
            routing_score=0.0,
            reason_codes=("ENVIRONMENT_ROUTE_BLOCKED",),
            reasons=("Market environment is not tradeable for new strategy candidates",),
        )

    priority = list(_REGIME_STRATEGIES.get(environment.primary_regime, ()))
    allowed = set(priority)
    direction = _preferred_direction(environment)
    score = max(environment.long_suitability_score, environment.short_suitability_score)
    codes.append("REGIME_ROUTE_APPLIED")
    reasons.append(f"{environment.primary_regime.value} strategy route applied")

    if environment.conflict_state is not ConflictState.NONE:
        score -= environment.conflict_score * 0.35
        codes.append("ROUTE_CONFLICT_PENALTY")
        reasons.append(f"{environment.conflict_state.value} reduced routing confidence")

    if environment.extension_state in {ExtensionState.OVEREXTENDED, ExtensionState.EXTREME}:
        allowed.discard(StrategyType.MOMENTUM_BREAKOUT)
        allowed.discard(StrategyType.MOMENTUM_SCALP)
        codes.append("CHASE_STRATEGIES_BLOCKED")
        reasons.append("Momentum chase strategies blocked because price is overextended")

    if environment.volatility_state is VolatilityState.EXTREME:
        allowed.discard(StrategyType.RANGE_REVERSAL)
        score -= 10.0
        codes.append("EXTREME_VOLATILITY_ROUTE_REDUCTION")
        reasons.append("Extreme volatility reduced strategy eligibility")

    if environment.primary_regime is MarketRegime.SQUEEZE:
        direction = PreferredDirection.NEUTRAL
        score = min(score, 60.0)
        codes.append("SQUEEZE_DIRECTION_UNCONFIRMED")
        reasons.append("Squeeze route waits for directional expansion evidence")

    ordered = tuple(strategy for strategy in priority if strategy in allowed)
    blocked = tuple(strategy for strategy in all_strategies if strategy not in allowed)
    return MarketStrategyRoute(
        allowed_strategies=ordered,
        blocked_strategies=blocked,
        preferred_direction=direction,
        strategy_priority=ordered,
        routing_score=round(max(0.0, min(100.0, score)), 6),
        reason_codes=tuple(dict.fromkeys(codes)),
        reasons=tuple(dict.fromkeys(reasons)),
    )


def strategy_allowed_for_direction(
    route: MarketStrategyRoute,
    strategy: StrategyType,
    direction: TradeDirection,
) -> bool:
    """Return whether a strategy and direction match the environment route."""

    if strategy not in route.allowed_strategies:
        return False
    if route.preferred_direction in {PreferredDirection.NEUTRAL, PreferredDirection.NONE}:
        return route.preferred_direction is PreferredDirection.NEUTRAL
    return direction.value == route.preferred_direction.value


def market_strategy_route_payload(route: MarketStrategyRoute) -> dict[str, object]:
    """Serialize an environment strategy route."""

    return {
        "allowed_strategies": [item.value for item in route.allowed_strategies],
        "blocked_strategies": [item.value for item in route.blocked_strategies],
        "preferred_direction": route.preferred_direction.value,
        "strategy_priority": [item.value for item in route.strategy_priority],
        "routing_score": route.routing_score,
        "reason_codes": list(route.reason_codes),
        "reasons": list(route.reasons),
    }


def _preferred_direction(environment: MarketEnvironment) -> PreferredDirection:
    bullish_biases = {
        HigherTimeframeBias.BULLISH,
        HigherTimeframeBias.STRONGLY_BULLISH,
    }
    bearish_biases = {
        HigherTimeframeBias.BEARISH,
        HigherTimeframeBias.STRONGLY_BEARISH,
    }
    if environment.higher_timeframe_bias in bullish_biases:
        return PreferredDirection.LONG
    if environment.higher_timeframe_bias in bearish_biases:
        return PreferredDirection.SHORT
    if environment.long_suitability_score >= environment.short_suitability_score + 10.0:
        return PreferredDirection.LONG
    if environment.short_suitability_score >= environment.long_suitability_score + 10.0:
        return PreferredDirection.SHORT
    return PreferredDirection.NEUTRAL
