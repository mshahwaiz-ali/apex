from __future__ import annotations

from apex.application.methodology_contracts import (
    EvidenceEffect,
    EvidenceFamily,
    EvidenceObservation,
)
from apex.application.methodology_strategy_contracts import PrimaryMarketState
from apex.application.methodology_strategy_evaluation import (
    StrategyEligibilityState,
    evaluate_strategy_eligibility,
    evaluate_strategy_registry,
    strategy_eligibility_evaluation_payload,
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


def test_strategy_is_compatible_when_state_and_mandatory_evidence_match() -> None:
    result = evaluate_strategy_eligibility(
        StrategyType.TREND_PULLBACK,
        market_state=PrimaryMarketState.PULLBACK_IN_UPTREND,
        evidence=_evidence(EvidenceFamily.STRUCTURE, EvidenceFamily.TREND),
    )

    assert result.state is StrategyEligibilityState.COMPATIBLE
    assert result.missing_mandatory_evidence == ()


def test_strategy_reports_incompatible_market_state() -> None:
    result = evaluate_strategy_eligibility(
        StrategyType.RANGE_REVERSAL,
        market_state=PrimaryMarketState.TRENDING_UP,
        evidence=_evidence(EvidenceFamily.STRUCTURE, EvidenceFamily.LIQUIDITY),
    )

    assert result.state is StrategyEligibilityState.INCOMPATIBLE_STATE


def test_strategy_reports_prohibited_chaotic_state() -> None:
    result = evaluate_strategy_eligibility(
        StrategyType.MOMENTUM_SCALP,
        market_state=PrimaryMarketState.CHAOTIC,
        evidence=_evidence(EvidenceFamily.MOMENTUM, EvidenceFamily.PARTICIPATION),
    )

    assert result.state is StrategyEligibilityState.PROHIBITED_STATE


def test_missing_canonical_evidence_is_not_reported_as_incompatible() -> None:
    result = evaluate_strategy_eligibility(
        StrategyType.MOMENTUM_BREAKOUT,
        market_state=PrimaryMarketState.BREAKOUT_ATTEMPT,
    )
    payload = strategy_eligibility_evaluation_payload(result)

    assert result.state is StrategyEligibilityState.INSUFFICIENT_EVIDENCE_METADATA
    assert payload["missing_mandatory_evidence"] == ["structure", "participation"]


def test_registry_evaluation_covers_every_strategy() -> None:
    results = evaluate_strategy_registry(
        market_state=PrimaryMarketState.RANGING,
        evidence=_evidence(EvidenceFamily.STRUCTURE, EvidenceFamily.LIQUIDITY),
    )

    assert {item.strategy for item in results} == set(StrategyType)
    assert len(results) == len(StrategyType)
