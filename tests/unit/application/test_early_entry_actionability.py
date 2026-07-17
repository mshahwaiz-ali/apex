"""Tests for controlled early-entry actionability."""

from apex.application.market_strategy_router import (
    MarketStrategyRoute,
    PreferredDirection,
)
from apex.application.near_current_entry import (
    EntryActionability,
    NearCurrentEntryDecision,
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


def _environment() -> MarketEnvironment:
    return MarketEnvironment(
        primary_regime=MarketRegime.BREAKOUT_RETEST_UP,
        higher_timeframe_bias=HigherTimeframeBias.BULLISH,
        execution_timeframe="5m",
        entry_timeframe="1m",
        alignment_score=82.0,
        conflict_score=5.0,
        conflict_state=ConflictState.NONE,
        volatility_state=VolatilityState.NORMAL,
        extension_state=ExtensionState.NORMAL,
        tradeable=True,
        long_suitability_score=84.0,
        short_suitability_score=16.0,
        reason_codes=(),
        reasons=(),
        missing_timeframes=(),
        input_completeness=InputCompleteness.COMPLETE,
        timeframe_regimes={},
    )


def _route() -> MarketStrategyRoute:
    allowed = (StrategyType.BREAKOUT_CONTINUATION,)
    return MarketStrategyRoute(
        allowed_strategies=allowed,
        blocked_strategies=tuple(
            strategy for strategy in StrategyType if strategy not in allowed
        ),
        preferred_direction=PreferredDirection.LONG,
        strategy_priority=allowed,
        routing_score=84.0,
        reason_codes=("TEST_ROUTE",),
        reasons=("test route",),
    )


def _precision(
    *,
    state: str,
    distance: float,
    score: float = 82.0,
) -> dict[str, object]:
    return {
        "entry_state": state,
        "score": score,
        "current_distance_from_ideal_pct": distance,
        "entry_zone_low": 99.0,
        "entry_zone_high": 101.0,
        "ideal_entry": 100.0,
        "maximum_chase_price": 102.0,
        "current_price": 100.2,
        "reclaim_trigger": 99.5,
        "retest_trigger": 101.0,
        "structural_invalidation": 95.0,
    }


def _evaluate(precision: dict[str, object]) -> NearCurrentEntryDecision:
    return evaluate_near_current_entry(
        precision,
        _environment(),
        _route(),
        selected_strategy=StrategyType.BREAKOUT_CONTINUATION,
        selected_direction=TradeDirection.LONG,
    )


def test_nearby_retest_can_be_aggressive_early_entry() -> None:
    decision = _evaluate(
        _precision(state="WAIT_FOR_RETEST", distance=0.20),
    )

    assert decision.entry_state == "WAIT_FOR_RETEST"
    assert decision.actionability is EntryActionability.AGGRESSIVE
    assert decision.actionable_now
    assert decision.immediate_entry_price == 100.2
    assert "EARLY_ENTRY_BEFORE_CONFIRMATION" in decision.warning_codes


def test_nearby_reclaim_can_be_aggressive_early_entry() -> None:
    decision = _evaluate(
        _precision(state="WAIT_FOR_RECLAIM", distance=0.15),
    )

    assert decision.entry_state == "WAIT_FOR_RECLAIM"
    assert decision.actionability is EntryActionability.AGGRESSIVE
    assert decision.actionable_now


def test_high_chase_wait_state_still_prefers_pullback() -> None:
    decision = _evaluate(
        _precision(state="WAIT_FOR_RETEST", distance=0.60),
    )

    assert decision.actionability is EntryActionability.PULLBACK_PREFERRED
    assert not decision.actionable_now
    assert "EARLY_ENTRY_BEFORE_CONFIRMATION" not in decision.warning_codes


def test_low_score_wait_state_is_not_forced_actionable() -> None:
    decision = _evaluate(
        _precision(state="WAIT_FOR_RECLAIM", distance=0.20, score=35.0),
    )

    assert decision.actionability is EntryActionability.PULLBACK_PREFERRED
    assert not decision.actionable_now


def test_close_approaching_entry_can_be_aggressive() -> None:
    decision = _evaluate(
        _precision(state="APPROACHING_ENTRY", distance=0.10),
    )

    assert decision.entry_state == "APPROACHING_ENTRY"
    assert decision.actionability is EntryActionability.AGGRESSIVE
    assert decision.actionable_now
