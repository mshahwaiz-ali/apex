"""Tests for combined structural and fused market-state classification."""

from apex.application.market_state import (
    MarketStateDirection,
    MarketStateTag,
    classify_market_state,
    market_state_payload,
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


def _environment(**overrides: object) -> MarketEnvironment:
    values: dict[str, object] = {
        "primary_regime": MarketRegime.BREAKOUT_EXPANSION_UP,
        "higher_timeframe_bias": HigherTimeframeBias.BULLISH,
        "execution_timeframe": "5m",
        "entry_timeframe": "1m",
        "alignment_score": 82.0,
        "conflict_score": 8.0,
        "conflict_state": ConflictState.NONE,
        "volatility_state": VolatilityState.EXPANDING,
        "extension_state": ExtensionState.NORMAL,
        "tradeable": True,
        "long_suitability_score": 84.0,
        "short_suitability_score": 16.0,
        "reason_codes": (),
        "reasons": (),
        "missing_timeframes": (),
        "input_completeness": InputCompleteness.COMPLETE,
        "timeframe_regimes": {},
    }
    values.update(overrides)
    return MarketEnvironment(**values)  # type: ignore[arg-type]


def test_classification_preserves_multiple_simultaneous_states() -> None:
    snapshot = classify_market_state(
        decision_regime="breakout_expansion",
        environment=_environment(
            extension_state=ExtensionState.OVEREXTENDED,
            conflict_state=ConflictState.EXTENSION_WARNING,
        ),
    )

    assert snapshot.primary_state is MarketStateTag.MOMENTUM_EXPANSION
    assert snapshot.active_states == (
        MarketStateTag.MOMENTUM_EXPANSION,
        MarketStateTag.BREAKOUT,
        MarketStateTag.EXTENSION_WARNING,
        MarketStateTag.CONFLICT_WARNING,
    )
    assert snapshot.direction is MarketStateDirection.LONG
    assert snapshot.confidence_score == 84.0


def test_untradeable_environment_is_explicit_primary_state() -> None:
    snapshot = classify_market_state(
        decision_regime="uncertain",
        environment=_environment(
            primary_regime=MarketRegime.UNTRADEABLE,
            tradeable=False,
            long_suitability_score=0.0,
            short_suitability_score=0.0,
        ),
    )

    assert snapshot.primary_state is MarketStateTag.UNTRADEABLE
    assert snapshot.active_states[0] is MarketStateTag.UNTRADEABLE
    assert snapshot.confidence_score == 0.0


def test_payload_is_stable_and_transparent() -> None:
    snapshot = classify_market_state(
        decision_regime="compression",
        environment=_environment(primary_regime=MarketRegime.SQUEEZE),
    )

    assert market_state_payload(snapshot) == {
        "primary_state": "compression",
        "active_states": ["compression"],
        "direction": "neutral",
        "decision_regime": "compression",
        "environment_regime": "SQUEEZE",
        "tradeable": True,
        "confidence_score": 84.0,
        "reason_codes": [
            "MARKET_STATE_CLASSIFIED",
            "ENVIRONMENT_SQUEEZE",
            "STRUCTURE_COMPRESSION",
        ],
        "reasons": [
            "fused environment classified as SQUEEZE",
            "decision-frame structure classified as compression",
        ],
    }
