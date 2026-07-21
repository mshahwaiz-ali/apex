"""Adapt existing fused market-state output to methodology taxonomy."""

from __future__ import annotations

from apex.application.market_state import (
    MarketStateDirection,
    MarketStateSnapshot,
    MarketStateTag,
)
from apex.application.methodology_strategy_contracts import (
    MarketStateClassification,
    PrimaryMarketState,
    SecondaryMarketCondition,
)
from apex.market_environment import MarketRegime

_PRIMARY_BY_TAG_AND_DIRECTION: dict[
    tuple[MarketStateTag, MarketStateDirection], PrimaryMarketState
] = {
    (MarketStateTag.DIRECTIONAL_TREND, MarketStateDirection.LONG): PrimaryMarketState.TRENDING_UP,
    (
        MarketStateTag.DIRECTIONAL_TREND,
        MarketStateDirection.SHORT,
    ): PrimaryMarketState.TRENDING_DOWN,
    (
        MarketStateTag.MOMENTUM_EXPANSION,
        MarketStateDirection.LONG,
    ): PrimaryMarketState.POST_BREAKOUT,
    (
        MarketStateTag.MOMENTUM_EXPANSION,
        MarketStateDirection.SHORT,
    ): PrimaryMarketState.POST_BREAKDOWN,
    (MarketStateTag.BREAKOUT, MarketStateDirection.LONG): PrimaryMarketState.BREAKOUT_ATTEMPT,
    (MarketStateTag.BREAKOUT, MarketStateDirection.SHORT): PrimaryMarketState.BREAKDOWN_ATTEMPT,
    (MarketStateTag.BREAKOUT_RETEST, MarketStateDirection.LONG): PrimaryMarketState.POST_BREAKOUT,
    (MarketStateTag.BREAKOUT_RETEST, MarketStateDirection.SHORT): PrimaryMarketState.POST_BREAKDOWN,
    (MarketStateTag.STABLE_RANGE, MarketStateDirection.NEUTRAL): PrimaryMarketState.RANGING,
    (MarketStateTag.COMPRESSION, MarketStateDirection.NEUTRAL): PrimaryMarketState.COMPRESSING,
    (MarketStateTag.REVERSAL, MarketStateDirection.LONG): PrimaryMarketState.REVERSAL_ATTEMPT_UP,
    (MarketStateTag.REVERSAL, MarketStateDirection.SHORT): PrimaryMarketState.REVERSAL_ATTEMPT_DOWN,
    (MarketStateTag.EXHAUSTION, MarketStateDirection.LONG): PrimaryMarketState.EXHAUSTED_UP,
    (MarketStateTag.EXHAUSTION, MarketStateDirection.SHORT): PrimaryMarketState.EXHAUSTED_DOWN,
    (MarketStateTag.CHAOTIC_VOLATILITY, MarketStateDirection.UNKNOWN): PrimaryMarketState.CHAOTIC,
    (MarketStateTag.UNTRADEABLE, MarketStateDirection.UNKNOWN): PrimaryMarketState.CHAOTIC,
    (MarketStateTag.UNKNOWN, MarketStateDirection.UNKNOWN): PrimaryMarketState.TRANSITIONAL,
}


def adapt_market_state(snapshot: MarketStateSnapshot) -> MarketStateClassification:
    """Translate the current fused classifier without changing its decision logic."""

    primary = _primary(snapshot)
    secondary: list[SecondaryMarketCondition] = []
    active = set(snapshot.active_states)

    if MarketStateTag.MOMENTUM_EXPANSION in active:
        secondary.append(SecondaryMarketCondition.VOLATILITY_EXPANSION)
    if MarketStateTag.COMPRESSION in active:
        secondary.append(SecondaryMarketCondition.VOLATILITY_CONTRACTION)
    if MarketStateTag.EXTENSION_WARNING in active:
        secondary.append(SecondaryMarketCondition.OVEREXTENDED)
    if MarketStateTag.FAILED_BREAKOUT in active:
        secondary.append(
            SecondaryMarketCondition.FAILED_BREAKOUT
            if snapshot.direction is not MarketStateDirection.SHORT
            else SecondaryMarketCondition.FAILED_BREAKDOWN
        )
    if MarketStateTag.CONFLICT_WARNING in active:
        secondary.append(SecondaryMarketCondition.MILD_HTF_CONFLICT)
    if _has_direct_structural_opposition(snapshot):
        secondary.append(SecondaryMarketCondition.DIRECT_STRUCTURAL_OPPOSITION)

    evidence_ids = tuple(dict.fromkeys((*snapshot.reason_codes, *snapshot.active_states)))
    normalized_ids = tuple(
        item.value if isinstance(item, MarketStateTag) else str(item) for item in evidence_ids
    )
    return MarketStateClassification(
        primary=primary,
        secondary=tuple(dict.fromkeys(secondary)),
        evidence_ids=normalized_ids,
        reason="; ".join(snapshot.reasons),
    )


def _has_direct_structural_opposition(snapshot: MarketStateSnapshot) -> bool:
    """Keep broad tradeability thresholds distinct from structural opposition."""

    return (
        MarketStateTag.CHAOTIC_VOLATILITY in snapshot.active_states
        or snapshot.environment_regime
        in {MarketRegime.UNTRADEABLE, MarketRegime.UNKNOWN, MarketRegime.NOISY}
    )


def _primary(snapshot: MarketStateSnapshot) -> PrimaryMarketState:
    direct = _PRIMARY_BY_TAG_AND_DIRECTION.get((snapshot.primary_state, snapshot.direction))
    if direct is not None:
        return direct
    if snapshot.primary_state is MarketStateTag.STABLE_RANGE:
        return PrimaryMarketState.RANGING
    if snapshot.primary_state is MarketStateTag.COMPRESSION:
        return PrimaryMarketState.COMPRESSING
    if snapshot.primary_state in {
        MarketStateTag.CHAOTIC_VOLATILITY,
        MarketStateTag.UNTRADEABLE,
    }:
        return PrimaryMarketState.CHAOTIC
    if snapshot.direction is MarketStateDirection.LONG:
        return PrimaryMarketState.TRENDING_UP
    if snapshot.direction is MarketStateDirection.SHORT:
        return PrimaryMarketState.TRENDING_DOWN
    return PrimaryMarketState.TRANSITIONAL


__all__ = ["adapt_market_state"]
