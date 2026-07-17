"""Tests for environment-aware strategy routing."""

from apex.application.market_strategy_router import (
    PreferredDirection,
    route_market_strategies,
)
from apex.market_environment import (
    ConflictState,
    ExtensionState,
    HigherTimeframeBias,
    InputCompleteness,
    MarketEnvironment,
    MarketRegime,
    VolatilityState,
)
from apex.strategies import StrategyType


def _environment(**overrides: object) -> MarketEnvironment:
    values: dict[str, object] = {
        "primary_regime": MarketRegime.BREAKOUT_RETEST_UP,
        "higher_timeframe_bias": HigherTimeframeBias.BULLISH,
        "execution_timeframe": "5m",
        "entry_timeframe": "1m",
        "alignment_score": 78.0,
        "conflict_score": 12.0,
        "conflict_state": ConflictState.NONE,
        "volatility_state": VolatilityState.EXPANDING,
        "extension_state": ExtensionState.MODERATE,
        "tradeable": True,
        "long_suitability_score": 78.0,
        "short_suitability_score": 22.0,
        "reason_codes": (),
        "reasons": (),
        "missing_timeframes": (),
        "input_completeness": InputCompleteness.COMPLETE,
        "timeframe_regimes": {},
    }
    values.update(overrides)
    return MarketEnvironment(**values)  # type: ignore[arg-type]


def test_breakout_retest_prefers_long_continuation() -> None:
    route = route_market_strategies(_environment())

    assert route.preferred_direction is PreferredDirection.LONG
    assert route.strategy_priority[0] is StrategyType.BREAKOUT_CONTINUATION
    assert StrategyType.TREND_PULLBACK in route.allowed_strategies
    assert route.routing_score == 78.0


def test_overextension_blocks_momentum_chase_strategies() -> None:
    route = route_market_strategies(
        _environment(extension_state=ExtensionState.OVEREXTENDED)
    )

    assert StrategyType.MOMENTUM_BREAKOUT not in route.allowed_strategies
    assert StrategyType.MOMENTUM_SCALP not in route.allowed_strategies
    assert "CHASE_STRATEGIES_BLOCKED" in route.reason_codes


def test_untradeable_environment_blocks_all_routes() -> None:
    route = route_market_strategies(
        _environment(tradeable=False, primary_regime=MarketRegime.UNTRADEABLE)
    )

    assert route.allowed_strategies == ()
    assert route.preferred_direction is PreferredDirection.NONE
    assert route.routing_score == 0.0

def test_failed_breakout_keeps_trend_pullback_fallback() -> None:
    route = route_market_strategies(
        _environment(primary_regime=MarketRegime.FAILED_BREAKOUT_UP)
    )

    assert route.strategy_priority[:2] == (
        StrategyType.LIQUIDITY_REJECTION_REVERSAL,
        StrategyType.FAILED_BREAKOUT_REVERSAL,
    )
    assert StrategyType.TREND_PULLBACK in route.allowed_strategies


def test_exhaustion_keeps_trend_pullback_fallback() -> None:
    route = route_market_strategies(
        _environment(primary_regime=MarketRegime.EXHAUSTION_DOWN)
    )

    assert StrategyType.TREND_PULLBACK in route.allowed_strategies
