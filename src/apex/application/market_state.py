"""Typed multi-state market classification for detailed analysis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.market_environment import (
    ConflictState,
    ExtensionState,
    MarketEnvironment,
    MarketRegime,
    VolatilityState,
)


class MarketStateTag(StrEnum):
    """Canonical market states that may coexist for one symbol."""

    DIRECTIONAL_TREND = "directional_trend"
    MOMENTUM_EXPANSION = "momentum_expansion"
    BREAKOUT = "breakout"
    BREAKOUT_RETEST = "breakout_retest"
    STABLE_RANGE = "stable_range"
    COMPRESSION = "compression"
    FAILED_BREAKOUT = "failed_breakout"
    REVERSAL = "reversal"
    EXHAUSTION = "exhaustion"
    CHAOTIC_VOLATILITY = "chaotic_volatility"
    LOW_PARTICIPATION_DRIFT = "low_participation_drift"
    EXTENSION_WARNING = "extension_warning"
    CONFLICT_WARNING = "conflict_warning"
    UNTRADEABLE = "untradeable"
    UNKNOWN = "unknown"


class MarketStateDirection(StrEnum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MarketStateSnapshot:
    """One explainable snapshot combining structure and fused environment."""

    primary_state: MarketStateTag
    active_states: tuple[MarketStateTag, ...]
    direction: MarketStateDirection
    decision_regime: str
    environment_regime: MarketRegime
    tradeable: bool
    confidence_score: float
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.decision_regime.strip():
            raise ValueError("decision regime cannot be empty")
        if not self.active_states:
            raise ValueError("market state snapshot requires at least one active state")
        if self.primary_state is not self.active_states[0]:
            raise ValueError("primary state must be the first active state")
        if len(set(self.active_states)) != len(self.active_states):
            raise ValueError("active market states must be unique")
        if not 0.0 <= self.confidence_score <= 100.0:
            raise ValueError("market state confidence must be between zero and 100")
        if not self.reason_codes or not self.reasons:
            raise ValueError("market state snapshot requires reasons and reason codes")


def classify_market_state(
    *,
    decision_regime: str,
    environment: MarketEnvironment,
) -> MarketStateSnapshot:
    """Combine existing classifiers into stable simultaneous market states."""

    primary = _primary_state(environment)
    states: list[MarketStateTag] = [primary]

    structural = _structural_state(decision_regime)
    if structural is not None and structural not in states:
        states.append(structural)

    if environment.volatility_state is VolatilityState.EXTREME:
        states.append(MarketStateTag.CHAOTIC_VOLATILITY)
    if environment.extension_state in {
        ExtensionState.OVEREXTENDED,
        ExtensionState.EXTREME,
    }:
        states.append(MarketStateTag.EXTENSION_WARNING)
    if environment.conflict_state is not ConflictState.NONE:
        states.append(MarketStateTag.CONFLICT_WARNING)
    if not environment.tradeable and MarketStateTag.UNTRADEABLE not in states:
        states.insert(0, MarketStateTag.UNTRADEABLE)
        primary = MarketStateTag.UNTRADEABLE

    active = tuple(dict.fromkeys(states))
    confidence = max(
        environment.long_suitability_score,
        environment.short_suitability_score,
    )
    if not environment.tradeable:
        confidence = 0.0

    codes = (
        "MARKET_STATE_CLASSIFIED",
        f"ENVIRONMENT_{environment.primary_regime.value}",
        f"STRUCTURE_{decision_regime.upper()}",
    )
    reasons = (
        f"fused environment classified as {environment.primary_regime.value}",
        f"decision-frame structure classified as {decision_regime}",
    )
    return MarketStateSnapshot(
        primary_state=primary,
        active_states=active,
        direction=_direction(environment.primary_regime),
        decision_regime=decision_regime,
        environment_regime=environment.primary_regime,
        tradeable=environment.tradeable,
        confidence_score=round(confidence, 6),
        reason_codes=codes,
        reasons=reasons,
    )


def market_state_payload(snapshot: MarketStateSnapshot) -> dict[str, object]:
    """Serialize a typed market-state snapshot."""

    return {
        "primary_state": snapshot.primary_state.value,
        "active_states": [state.value for state in snapshot.active_states],
        "direction": snapshot.direction.value,
        "decision_regime": snapshot.decision_regime,
        "environment_regime": snapshot.environment_regime.value,
        "tradeable": snapshot.tradeable,
        "confidence_score": snapshot.confidence_score,
        "reason_codes": list(snapshot.reason_codes),
        "reasons": list(snapshot.reasons),
    }


def _primary_state(environment: MarketEnvironment) -> MarketStateTag:
    mapping = {
        MarketRegime.TREND_UP: MarketStateTag.DIRECTIONAL_TREND,
        MarketRegime.TREND_DOWN: MarketStateTag.DIRECTIONAL_TREND,
        MarketRegime.RANGE: MarketStateTag.STABLE_RANGE,
        MarketRegime.BREAKOUT_EXPANSION_UP: MarketStateTag.MOMENTUM_EXPANSION,
        MarketRegime.BREAKOUT_EXPANSION_DOWN: MarketStateTag.MOMENTUM_EXPANSION,
        MarketRegime.BREAKOUT_RETEST_UP: MarketStateTag.BREAKOUT_RETEST,
        MarketRegime.BREAKOUT_RETEST_DOWN: MarketStateTag.BREAKOUT_RETEST,
        MarketRegime.FAILED_BREAKOUT_UP: MarketStateTag.FAILED_BREAKOUT,
        MarketRegime.FAILED_BREAKOUT_DOWN: MarketStateTag.FAILED_BREAKOUT,
        MarketRegime.SQUEEZE: MarketStateTag.COMPRESSION,
        MarketRegime.EXHAUSTION_UP: MarketStateTag.EXHAUSTION,
        MarketRegime.EXHAUSTION_DOWN: MarketStateTag.EXHAUSTION,
        MarketRegime.REVERSAL_UP: MarketStateTag.REVERSAL,
        MarketRegime.REVERSAL_DOWN: MarketStateTag.REVERSAL,
        MarketRegime.NOISY: MarketStateTag.CHAOTIC_VOLATILITY,
        MarketRegime.UNTRADEABLE: MarketStateTag.UNTRADEABLE,
        MarketRegime.UNKNOWN: MarketStateTag.UNKNOWN,
    }
    return mapping[environment.primary_regime]


def _structural_state(decision_regime: str) -> MarketStateTag | None:
    mapping = {
        "strong_uptrend": MarketStateTag.DIRECTIONAL_TREND,
        "weak_uptrend": MarketStateTag.DIRECTIONAL_TREND,
        "strong_downtrend": MarketStateTag.DIRECTIONAL_TREND,
        "weak_downtrend": MarketStateTag.DIRECTIONAL_TREND,
        "stable_range": MarketStateTag.STABLE_RANGE,
        "volatile_range": MarketStateTag.STABLE_RANGE,
        "compression": MarketStateTag.COMPRESSION,
        "breakout_expansion": MarketStateTag.BREAKOUT,
        "reversal_transition": MarketStateTag.REVERSAL,
        "high_volatility_chaos": MarketStateTag.CHAOTIC_VOLATILITY,
        "low_volatility_stagnation": MarketStateTag.LOW_PARTICIPATION_DRIFT,
        "low_liquidity": MarketStateTag.LOW_PARTICIPATION_DRIFT,
        "uncertain": MarketStateTag.UNKNOWN,
    }
    return mapping.get(decision_regime)


def _direction(regime: MarketRegime) -> MarketStateDirection:
    if regime.value.endswith("_UP") or regime is MarketRegime.TREND_UP:
        return MarketStateDirection.LONG
    if regime.value.endswith("_DOWN") or regime is MarketRegime.TREND_DOWN:
        return MarketStateDirection.SHORT
    if regime in {MarketRegime.RANGE, MarketRegime.SQUEEZE}:
        return MarketStateDirection.NEUTRAL
    return MarketStateDirection.UNKNOWN
