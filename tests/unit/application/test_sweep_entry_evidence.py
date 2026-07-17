"""Tests for liquidity-sweep evidence in entry actionability."""

from apex.application.market_strategy_router import route_market_strategies
from apex.application.near_current_entry import (
    SweepAlignment,
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


def _environment() -> MarketEnvironment:
    return MarketEnvironment(
        primary_regime=MarketRegime.BREAKOUT_RETEST_UP,
        higher_timeframe_bias=HigherTimeframeBias.BULLISH,
        execution_timeframe="5m",
        entry_timeframe="1m",
        alignment_score=80.0,
        conflict_score=10.0,
        conflict_state=ConflictState.NONE,
        volatility_state=VolatilityState.NORMAL,
        extension_state=ExtensionState.MODERATE,
        tradeable=True,
        long_suitability_score=80.0,
        short_suitability_score=20.0,
        reason_codes=(),
        reasons=(),
        missing_timeframes=(),
        input_completeness=InputCompleteness.COMPLETE,
        timeframe_regimes={},
    )


def _precision() -> dict[str, object]:
    return {
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


def _candidate(side: str, recovery: float = 0.8) -> dict[str, object]:
    return {
        "evidence": {
            "supporting": [f"confirmed {side} liquidity sweep"],
        },
        "metadata": {"close_recovery": recovery},
    }


def test_sell_side_sweep_supports_long_entry() -> None:
    environment = _environment()
    decision = evaluate_near_current_entry(
        _precision(),
        environment,
        route_market_strategies(environment),
        selected_strategy=StrategyType.LIQUIDITY_REVERSAL,
        selected_direction=TradeDirection.LONG,
        selected_candidate=_candidate("sell_side"),
    )

    assert decision.sweep_alignment is SweepAlignment.SUPPORTIVE
    assert decision.sweep_side == "sell_side"
    assert decision.sweep_strength == 0.8
    assert "SUPPORTIVE_LIQUIDITY_SWEEP" in decision.reason_codes


def test_buy_side_sweep_warns_long_entry_without_hard_block() -> None:
    environment = _environment()
    decision = evaluate_near_current_entry(
        _precision(),
        environment,
        route_market_strategies(environment),
        selected_strategy=StrategyType.LIQUIDITY_REVERSAL,
        selected_direction=TradeDirection.LONG,
        selected_candidate=_candidate("buy_side"),
    )

    assert decision.entry_state == "READY_NOW"
    assert decision.sweep_alignment is SweepAlignment.OPPOSING
    assert "OPPOSING_LIQUIDITY_SWEEP" in decision.warning_codes


def test_non_sweep_candidate_has_no_sweep_alignment() -> None:
    environment = _environment()
    decision = evaluate_near_current_entry(
        _precision(),
        environment,
        route_market_strategies(environment),
        selected_direction=TradeDirection.LONG,
        selected_candidate={"evidence": {"supporting": ["trend continuation"]}},
    )

    assert decision.sweep_alignment is SweepAlignment.NONE
    assert decision.sweep_side is None
    assert decision.sweep_strength is None


def test_payload_serializes_sweep_evidence() -> None:
    environment = _environment()
    decision = evaluate_near_current_entry(
        _precision(),
        environment,
        route_market_strategies(environment),
        selected_direction=TradeDirection.SHORT,
        selected_candidate=_candidate("buy_side", recovery=1.4),
    )
    payload = near_current_entry_payload(decision)

    assert payload["sweep_alignment"] == "SUPPORTIVE"
    assert payload["sweep_side"] == "buy_side"
    assert payload["sweep_strength"] == 1.0
