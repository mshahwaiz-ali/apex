"""Tests for environment-aware near-current entry decisions."""

from apex.application.market_strategy_router import route_market_strategies
from apex.application.near_current_entry import (
    ChaseRisk,
    EntryActionability,
    evaluate_near_current_entry,
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
from apex.strategies import StrategyType, TradeDirection


def _environment(**overrides: object) -> MarketEnvironment:
    values: dict[str, object] = {
        "primary_regime": MarketRegime.BREAKOUT_RETEST_UP,
        "higher_timeframe_bias": HigherTimeframeBias.BULLISH,
        "execution_timeframe": "5m",
        "entry_timeframe": "1m",
        "alignment_score": 80.0,
        "conflict_score": 10.0,
        "conflict_state": ConflictState.NONE,
        "volatility_state": VolatilityState.NORMAL,
        "extension_state": ExtensionState.MODERATE,
        "tradeable": True,
        "long_suitability_score": 80.0,
        "short_suitability_score": 20.0,
        "reason_codes": (),
        "reasons": (),
        "missing_timeframes": (),
        "input_completeness": InputCompleteness.COMPLETE,
        "timeframe_regimes": {},
    }
    values.update(overrides)
    return MarketEnvironment(**values)  # type: ignore[arg-type]


def _precision(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "entry_state": "READY_NOW",
        "entry_zone_low": 99.8,
        "entry_zone_high": 100.2,
        "ideal_entry": 100.0,
        "current_price": 100.1,
        "current_distance_from_ideal_pct": 0.1,
        "maximum_chase_price": 100.5,
        "reclaim_trigger": 100.2,
        "retest_trigger": 100.0,
        "structural_invalidation": 99.0,
        "score": 82.0,
    }
    values.update(overrides)
    return values


def test_ready_now_entry_remains_actionable_near_ideal() -> None:
    environment = _environment()
    route = route_market_strategies(environment)

    decision = evaluate_near_current_entry(_precision(), environment, route)

    assert decision.entry_state == "READY_NOW"
    assert decision.actionable_now is True
    assert decision.chase_risk is ChaseRisk.LOW
    assert decision.entry_quality_score is not None
    assert decision.entry_quality_score > 75.0


def test_high_chase_risk_prefers_pullback_without_rewriting_state() -> None:
    environment = _environment()
    route = route_market_strategies(environment)

    decision = evaluate_near_current_entry(
        _precision(current_distance_from_ideal_pct=0.6),
        environment,
        route,
    )

    assert decision.entry_state == "READY_NOW"
    assert decision.actionability is EntryActionability.PULLBACK_PREFERRED
    assert decision.actionable_now is False
    assert decision.chase_risk is ChaseRisk.HIGH
    assert "READY_NOW_HIGH_CHASE_RISK" in decision.warning_codes


def test_extreme_extension_marks_entry_missed() -> None:
    environment = _environment(extension_state=ExtensionState.EXTREME)
    route = route_market_strategies(environment)

    decision = evaluate_near_current_entry(_precision(), environment, route)

    assert decision.entry_state == "MISSED_ENTRY"
    assert decision.chase_risk is ChaseRisk.EXTREME
    assert decision.actionable_now is False


def test_selected_setup_conflicting_with_route_is_warned() -> None:
    environment = _environment()
    route = route_market_strategies(environment)

    decision = evaluate_near_current_entry(
        _precision(),
        environment,
        route,
        selected_strategy=StrategyType.RANGE_REVERSAL,
        selected_direction=TradeDirection.SHORT,
    )

    assert decision.entry_state == "READY_NOW"
    assert decision.actionability is EntryActionability.AGGRESSIVE
    assert decision.actionable_now is True
    assert "SELECTED_SETUP_ROUTE_CONFLICT" in decision.warning_codes


def test_missing_precision_plan_returns_no_trade() -> None:
    environment = _environment()
    route = route_market_strategies(environment)

    decision = evaluate_near_current_entry(None, environment, route)

    assert decision.entry_state == "NO_TRADE"
    assert decision.entry_quality_score is None
    assert decision.chase_risk is None
    assert decision.actionable_now is False
