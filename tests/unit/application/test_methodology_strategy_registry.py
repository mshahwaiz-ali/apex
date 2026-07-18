from __future__ import annotations

from apex.application.methodology_contracts import EvidenceFamily
from apex.application.methodology_strategy_contracts import (
    ConfirmationPolicy,
    PrimaryMarketState,
)
from apex.application.methodology_strategy_registry import (
    METHODOLOGY_STRATEGY_REGISTRY,
    strategy_eligibility,
    strategy_registry_payload,
)
from apex.strategies.strategy_types import StrategyType


def test_registry_covers_every_strategy_exactly_once() -> None:
    assert set(METHODOLOGY_STRATEGY_REGISTRY) == set(StrategyType)
    assert len(METHODOLOGY_STRATEGY_REGISTRY) == len(StrategyType)


def test_every_strategy_has_complete_methodology_declaration() -> None:
    for strategy, eligibility in METHODOLOGY_STRATEGY_REGISTRY.items():
        assert eligibility.strategy_id == strategy.value
        assert eligibility.compatible_states
        assert eligibility.mandatory_evidence
        assert eligibility.entry_models
        assert eligibility.target_methods
        assert eligibility.historical_segment_key == f"{strategy.value}:v1"
        assert PrimaryMarketState.CHAOTIC in eligibility.prohibited_states


def test_trend_pullback_requires_structure_and_trend() -> None:
    eligibility = strategy_eligibility(StrategyType.TREND_PULLBACK)

    assert eligibility.mandatory_evidence == (
        EvidenceFamily.STRUCTURE,
        EvidenceFamily.TREND,
    )
    assert eligibility.confirmation_policy is (
        ConfirmationPolicy.LOWER_TIMEFRAME_CONFIRMATION_ALLOWED
    )
    assert PrimaryMarketState.PULLBACK_IN_UPTREND in eligibility.compatible_states
    assert PrimaryMarketState.RALLY_IN_DOWNTREND in eligibility.compatible_states


def test_range_and_exhaustion_strategies_are_state_specific() -> None:
    range_reversal = strategy_eligibility(StrategyType.RANGE_REVERSAL)
    exhaustion = strategy_eligibility(StrategyType.EXHAUSTION_REVERSAL)

    assert range_reversal.compatible_states == (PrimaryMarketState.RANGING,)
    assert exhaustion.compatible_states == (
        PrimaryMarketState.EXHAUSTED_UP,
        PrimaryMarketState.EXHAUSTED_DOWN,
    )


def test_registry_payload_is_stable_and_public_safe() -> None:
    payload = strategy_registry_payload()
    trend = payload[StrategyType.TREND_PULLBACK.value]

    assert set(payload) == {strategy.value for strategy in StrategyType}
    assert trend["strategy_version"] == "1"
    assert trend["mandatory_evidence"] == ["structure", "trend"]
    assert trend["confirmation_policy"] == "lower_timeframe_confirmation_allowed"
    assert trend["historical_segment_key"] == "trend_pullback:v1"
