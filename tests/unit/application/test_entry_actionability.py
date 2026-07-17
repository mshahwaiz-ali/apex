"""Tests for simplified near-current entry actionability."""

from apex.application.market_strategy_router import (
    MarketStrategyRoute,
    PreferredDirection,
)
from apex.application.near_current_entry import (
    EntryActionability,
    evaluate_near_current_entry,
    near_current_entry_payload,
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


def _environment(*, tradeable: bool = True) -> MarketEnvironment:
    return MarketEnvironment(
        primary_regime=MarketRegime.TREND_UP,
        higher_timeframe_bias=HigherTimeframeBias.BULLISH,
        execution_timeframe="5m",
        entry_timeframe="1m",
        alignment_score=80.0,
        conflict_score=0.0,
        conflict_state=ConflictState.NONE,
        volatility_state=VolatilityState.NORMAL,
        extension_state=ExtensionState.NORMAL,
        tradeable=tradeable,
        long_suitability_score=80.0,
        short_suitability_score=20.0,
        reason_codes=(),
        reasons=(),
        missing_timeframes=(),
        input_completeness=InputCompleteness.COMPLETE,
        timeframe_regimes={},
    )


def _route(*, allow_breakout: bool = True) -> MarketStrategyRoute:
    allowed = (
        (StrategyType.BREAKOUT_CONTINUATION,)
        if allow_breakout
        else (StrategyType.TREND_PULLBACK,)
    )
    return MarketStrategyRoute(
        allowed_strategies=allowed,
        blocked_strategies=tuple(
            strategy for strategy in StrategyType if strategy not in allowed
        ),
        preferred_direction=PreferredDirection.LONG,
        strategy_priority=allowed,
        routing_score=80.0,
        reason_codes=("TEST_ROUTE",),
        reasons=("test route",),
    )


def _precision(*, distance: float = 0.10) -> dict[str, object]:
    return {
        "entry_state": "READY_NOW",
        "score": 82.0,
        "current_distance_from_ideal_pct": distance,
        "entry_zone_low": 99.0,
        "entry_zone_high": 101.0,
        "ideal_entry": 100.0,
        "maximum_chase_price": 102.0,
        "current_price": 100.1,
        "reclaim_trigger": 99.0,
        "retest_trigger": 101.0,
        "structural_invalidation": 95.0,
    }


def test_ready_entry_exposes_immediate_and_preferred_prices() -> None:
    decision = evaluate_near_current_entry(
        _precision(),
        _environment(),
        _route(),
        selected_strategy=StrategyType.BREAKOUT_CONTINUATION,
        selected_direction=TradeDirection.LONG,
    )

    assert decision.actionability is EntryActionability.READY
    assert decision.actionable_now
    assert decision.immediate_entry_price == 100.1
    assert decision.preferred_entry_price == 100.0


def test_high_chase_ready_entry_prefers_pullback_without_wait_state_rewrite() -> None:
    decision = evaluate_near_current_entry(
        _precision(distance=0.60),
        _environment(),
        _route(),
        selected_strategy=StrategyType.BREAKOUT_CONTINUATION,
        selected_direction=TradeDirection.LONG,
    )

    assert decision.entry_state == "READY_NOW"
    assert decision.actionability is EntryActionability.PULLBACK_PREFERRED
    assert not decision.actionable_now
    assert "READY_NOW_HIGH_CHASE_RISK" in decision.warning_codes


def test_route_conflict_is_warning_not_automatic_no_trade() -> None:
    decision = evaluate_near_current_entry(
        _precision(),
        _environment(),
        _route(allow_breakout=False),
        selected_strategy=StrategyType.BREAKOUT_CONTINUATION,
        selected_direction=TradeDirection.LONG,
    )

    assert decision.entry_state == "READY_NOW"
    assert decision.actionability is EntryActionability.AGGRESSIVE
    assert decision.actionable_now
    assert "SELECTED_SETUP_ROUTE_CONFLICT" in decision.warning_codes


def test_untradeable_environment_remains_hard_invalid() -> None:
    decision = evaluate_near_current_entry(
        _precision(),
        _environment(tradeable=False),
        _route(),
        selected_strategy=StrategyType.BREAKOUT_CONTINUATION,
        selected_direction=TradeDirection.LONG,
    )

    assert decision.entry_state == "NO_TRADE"
    assert decision.actionability is EntryActionability.INVALID
    assert not decision.actionable_now


def test_payload_serializes_simplified_entry_fields() -> None:
    decision = evaluate_near_current_entry(
        _precision(),
        _environment(),
        _route(),
        selected_strategy=StrategyType.BREAKOUT_CONTINUATION,
        selected_direction=TradeDirection.LONG,
    )
    payload = near_current_entry_payload(decision)

    assert payload["actionability"] == "READY"
    assert payload["immediate_entry_price"] == 100.1
    assert payload["preferred_entry_price"] == 100.0
    assert payload["warnings"] == []
