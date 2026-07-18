from __future__ import annotations

from apex.application.methodology_contracts import (
    EvidenceEffect,
    EvidenceFamily,
    EvidenceObservation,
)
from apex.application.methodology_strategy_contracts import PrimaryMarketState
from apex.application.methodology_strategy_enforcement import (
    StrategyEnforcementAction,
    derive_strategy_enforcement,
    derive_strategy_enforcement_registry,
    strategy_enforcement_payload,
)
from apex.application.methodology_strategy_evaluation import (
    evaluate_strategy_eligibility,
    evaluate_strategy_registry,
)
from apex.strategies.strategy_types import StrategyType


def _evidence(*families: EvidenceFamily) -> tuple[EvidenceObservation, ...]:
    return tuple(
        EvidenceObservation(
            family=family,
            source=f"test_{family.value}",
            normalized_strength=0.8,
            freshness=1.0,
            independence_group=family.value,
            effect=EvidenceEffect.SUPPORTS,
            reason=f"{family.value} evidence is present",
        )
        for family in families
    )


def test_compatible_strategy_is_allowed() -> None:
    evaluation = evaluate_strategy_eligibility(
        StrategyType.TREND_PULLBACK,
        market_state=PrimaryMarketState.PULLBACK_IN_UPTREND,
        evidence=_evidence(EvidenceFamily.STRUCTURE, EvidenceFamily.TREND),
    )

    decision = derive_strategy_enforcement(evaluation)

    assert decision.action is StrategyEnforcementAction.ALLOW
    assert decision.reason_codes == ("METHODOLOGY_COMPATIBLE",)


def test_incompatible_and_prohibited_states_are_suppressed() -> None:
    incompatible = derive_strategy_enforcement(
        evaluate_strategy_eligibility(
            StrategyType.RANGE_REVERSAL,
            market_state=PrimaryMarketState.TRENDING_UP,
            evidence=_evidence(EvidenceFamily.STRUCTURE, EvidenceFamily.LIQUIDITY),
        )
    )
    prohibited = derive_strategy_enforcement(
        evaluate_strategy_eligibility(
            StrategyType.MOMENTUM_SCALP,
            market_state=PrimaryMarketState.CHAOTIC,
            evidence=_evidence(EvidenceFamily.MOMENTUM, EvidenceFamily.PARTICIPATION),
        )
    )

    assert incompatible.action is StrategyEnforcementAction.SUPPRESS
    assert incompatible.reason_codes == ("METHODOLOGY_INCOMPATIBLE_STATE",)
    assert prohibited.action is StrategyEnforcementAction.SUPPRESS
    assert prohibited.reason_codes == ("METHODOLOGY_PROHIBITED_STATE",)


def test_missing_metadata_is_deferred_not_suppressed() -> None:
    evaluation = evaluate_strategy_eligibility(
        StrategyType.MOMENTUM_BREAKOUT,
        market_state=PrimaryMarketState.BREAKOUT_ATTEMPT,
    )

    decision = derive_strategy_enforcement(evaluation)
    payload = strategy_enforcement_payload(decision)

    assert decision.action is StrategyEnforcementAction.DEFER
    assert payload["action"] == "defer"
    assert payload["reason_codes"] == ["METHODOLOGY_METADATA_INCOMPLETE"]


def test_registry_enforcement_preserves_strategy_order_and_coverage() -> None:
    evaluations = evaluate_strategy_registry(
        market_state=PrimaryMarketState.RANGING,
        evidence=_evidence(EvidenceFamily.STRUCTURE, EvidenceFamily.LIQUIDITY),
    )

    decisions = derive_strategy_enforcement_registry(evaluations)

    assert tuple(item.strategy for item in decisions) == tuple(StrategyType)
    assert len(decisions) == len(StrategyType)
