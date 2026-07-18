from __future__ import annotations

from apex.application.market_state import (
    MarketStateDirection,
    MarketStateSnapshot,
    MarketStateTag,
)
from apex.application.methodology_market_state import adapt_market_state
from apex.application.methodology_strategy_contracts import (
    PrimaryMarketState,
    SecondaryMarketCondition,
)
from apex.market_environment import MarketRegime


def _snapshot(
    *,
    primary: MarketStateTag,
    direction: MarketStateDirection,
    active: tuple[MarketStateTag, ...] | None = None,
    tradeable: bool = True,
) -> MarketStateSnapshot:
    return MarketStateSnapshot(
        primary_state=primary,
        active_states=active or (primary,),
        direction=direction,
        decision_regime="stable_range",
        environment_regime=MarketRegime.RANGE,
        tradeable=tradeable,
        confidence_score=70.0 if tradeable else 0.0,
        reason_codes=("MARKET_STATE_CLASSIFIED",),
        reasons=("existing fused classifier result",),
    )


def test_directional_market_state_maps_to_trade_plan_primary_state() -> None:
    long_state = adapt_market_state(
        _snapshot(
            primary=MarketStateTag.DIRECTIONAL_TREND,
            direction=MarketStateDirection.LONG,
        )
    )
    short_state = adapt_market_state(
        _snapshot(
            primary=MarketStateTag.DIRECTIONAL_TREND,
            direction=MarketStateDirection.SHORT,
        )
    )

    assert long_state.primary is PrimaryMarketState.TRENDING_UP
    assert short_state.primary is PrimaryMarketState.TRENDING_DOWN


def test_compression_and_extension_become_secondary_conditions() -> None:
    classification = adapt_market_state(
        _snapshot(
            primary=MarketStateTag.COMPRESSION,
            direction=MarketStateDirection.NEUTRAL,
            active=(MarketStateTag.COMPRESSION, MarketStateTag.EXTENSION_WARNING),
        )
    )

    assert classification.primary is PrimaryMarketState.COMPRESSING
    assert SecondaryMarketCondition.VOLATILITY_CONTRACTION in classification.secondary
    assert SecondaryMarketCondition.OVEREXTENDED in classification.secondary


def test_failed_break_and_conflict_are_preserved() -> None:
    classification = adapt_market_state(
        _snapshot(
            primary=MarketStateTag.FAILED_BREAKOUT,
            direction=MarketStateDirection.SHORT,
            active=(MarketStateTag.FAILED_BREAKOUT, MarketStateTag.CONFLICT_WARNING),
        )
    )

    assert SecondaryMarketCondition.FAILED_BREAKDOWN in classification.secondary
    assert SecondaryMarketCondition.MILD_HTF_CONFLICT in classification.secondary


def test_untradeable_state_maps_to_chaotic_with_direct_opposition() -> None:
    classification = adapt_market_state(
        _snapshot(
            primary=MarketStateTag.UNTRADEABLE,
            direction=MarketStateDirection.UNKNOWN,
            tradeable=False,
        )
    )

    assert classification.primary is PrimaryMarketState.CHAOTIC
    assert SecondaryMarketCondition.DIRECT_STRUCTURAL_OPPOSITION in classification.secondary
