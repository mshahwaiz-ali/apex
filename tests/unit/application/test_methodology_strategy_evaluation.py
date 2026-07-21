from __future__ import annotations

from apex.application.methodology_contracts import (
    EvidenceEffect,
    EvidenceFamily,
    EvidenceObservation,
)
from apex.application.methodology_strategy_contracts import PrimaryMarketState
from apex.application.methodology_strategy_evaluation import (
    EligibilityStage,
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


def test_scalp_lane_allows_broader_state_with_runner_disabled() -> None:
    from apex.application.methodology_opportunity_context import HoldingHorizon, OpportunityLane
    from apex.strategies.contracts import TradeDirection

    result = evaluate_strategy_eligibility(
        StrategyType.MOMENTUM_SCALP,
        market_state=PrimaryMarketState.EXHAUSTED_UP,
        evidence=_evidence(EvidenceFamily.MOMENTUM, EvidenceFamily.PARTICIPATION),
        lane=OpportunityLane.CMP_SCALP,
        direction=TradeDirection.SHORT,
        holding_horizon=HoldingHorizon.SCALP,
    )

    assert result.state is StrategyEligibilityState.COMPATIBLE_WITH_CONSTRAINTS
    assert result.runner_allowed is False
    assert "warning and target ceiling" in result.reasons[0]


def test_runner_lane_keeps_incompatible_state_strict() -> None:
    from apex.application.methodology_opportunity_context import HoldingHorizon, OpportunityLane
    from apex.strategies.contracts import TradeDirection

    result = evaluate_strategy_eligibility(
        StrategyType.MOMENTUM_SCALP,
        market_state=PrimaryMarketState.EXHAUSTED_UP,
        evidence=_evidence(EvidenceFamily.MOMENTUM, EvidenceFamily.PARTICIPATION),
        lane=OpportunityLane.RUNNER,
        direction=TradeDirection.SHORT,
        holding_horizon=HoldingHorizon.RUNNER,
    )

    assert result.state is StrategyEligibilityState.INCOMPATIBLE_STATE


def test_scalp_lane_cannot_bypass_missing_mandatory_evidence() -> None:
    from apex.application.methodology_opportunity_context import HoldingHorizon, OpportunityLane
    from apex.strategies.contracts import TradeDirection

    result = evaluate_strategy_eligibility(
        StrategyType.MOMENTUM_SCALP,
        market_state=PrimaryMarketState.EXHAUSTED_UP,
        evidence=(),
        lane=OpportunityLane.CMP_SCALP,
        direction=TradeDirection.SHORT,
        holding_horizon=HoldingHorizon.SCALP,
    )

    assert result.state is StrategyEligibilityState.INSUFFICIENT_EVIDENCE_METADATA
    assert result.runner_allowed is False
    assert result.missing_mandatory_evidence == (
        EvidenceFamily.MOMENTUM,
        EvidenceFamily.PARTICIPATION,
    )
    assert result.reasons[0].startswith("mandatory_evidence stage rejected candidate")


def test_missing_evidence_precedes_prohibited_state() -> None:
    result = evaluate_strategy_eligibility(
        StrategyType.MOMENTUM_SCALP,
        market_state=PrimaryMarketState.CHAOTIC,
        evidence=(),
    )

    assert result.state is StrategyEligibilityState.INSUFFICIENT_EVIDENCE_METADATA
    assert result.missing_mandatory_evidence
    assert "mandatory_evidence stage" in result.reasons[0]


def test_prohibited_state_remains_strict_when_evidence_is_complete() -> None:
    result = evaluate_strategy_eligibility(
        StrategyType.MOMENTUM_SCALP,
        market_state=PrimaryMarketState.CHAOTIC,
        evidence=_evidence(
            EvidenceFamily.MOMENTUM,
            EvidenceFamily.PARTICIPATION,
        ),
    )

    assert result.state is StrategyEligibilityState.PROHIBITED_STATE
    assert result.missing_mandatory_evidence == ()


def test_missing_state_is_distinct_after_evidence_is_complete() -> None:
    result = evaluate_strategy_eligibility(
        StrategyType.MOMENTUM_SCALP,
        market_state=None,
        evidence=_evidence(
            EvidenceFamily.MOMENTUM,
            EvidenceFamily.PARTICIPATION,
        ),
    )

    assert result.state is StrategyEligibilityState.INSUFFICIENT_EVIDENCE_METADATA
    assert result.missing_mandatory_evidence == ()
    assert result.runner_allowed is False
    assert result.reasons == (
        "market_state stage rejected candidate; canonical state is unavailable",
    )


def test_stale_data_rejects_before_mandatory_evidence() -> None:
    result = evaluate_strategy_eligibility(
        StrategyType.MOMENTUM_SCALP,
        market_state=PrimaryMarketState.TRENDING_UP,
        evidence=(),
        data_fresh=False,
    )

    assert result.stage is EligibilityStage.DATA
    assert result.state is StrategyEligibilityState.INSUFFICIENT_EVIDENCE_METADATA
    assert result.reasons == ("data stage rejected candidate; market data is stale",)


def test_invalid_stop_rejects_before_market_state_exception() -> None:
    from apex.application.methodology_opportunity_context import HoldingHorizon, OpportunityLane

    result = evaluate_strategy_eligibility(
        StrategyType.MOMENTUM_SCALP,
        market_state=PrimaryMarketState.EXHAUSTED_UP,
        evidence=_evidence(
            EvidenceFamily.MOMENTUM,
            EvidenceFamily.PARTICIPATION,
        ),
        lane=OpportunityLane.CMP_SCALP,
        holding_horizon=HoldingHorizon.SCALP,
        stop_valid=False,
    )

    assert result.stage is EligibilityStage.GEOMETRY
    assert result.state is StrategyEligibilityState.PROHIBITED_STATE
    assert "invalid stop geometry" in result.reasons[0]


def test_missing_target_rejects_at_geometry_stage() -> None:
    result = evaluate_strategy_eligibility(
        StrategyType.TREND_PULLBACK,
        market_state=PrimaryMarketState.PULLBACK_IN_UPTREND,
        evidence=_evidence(EvidenceFamily.STRUCTURE, EvidenceFamily.TREND),
        has_target=False,
    )

    assert result.stage is EligibilityStage.GEOMETRY
    assert "missing target geometry" in result.reasons[0]


def test_true_local_chaos_rejects_independently_of_htf_conflict() -> None:
    result = evaluate_strategy_eligibility(
        StrategyType.TREND_PULLBACK,
        market_state=PrimaryMarketState.PULLBACK_IN_UPTREND,
        evidence=_evidence(EvidenceFamily.STRUCTURE, EvidenceFamily.TREND),
        execution_chaos=True,
        htf_directional_conflict=False,
    )

    assert result.stage is EligibilityStage.EXECUTION_STATE
    assert result.state is StrategyEligibilityState.PROHIBITED_STATE


def test_htf_disagreement_alone_is_not_execution_chaos() -> None:
    result = evaluate_strategy_eligibility(
        StrategyType.TREND_PULLBACK,
        market_state=PrimaryMarketState.PULLBACK_IN_UPTREND,
        evidence=_evidence(EvidenceFamily.STRUCTURE, EvidenceFamily.TREND),
        execution_chaos=False,
        htf_directional_conflict=True,
    )
    payload = strategy_eligibility_evaluation_payload(result)

    assert result.state is StrategyEligibilityState.COMPATIBLE
    assert result.stage is EligibilityStage.COMPLETE
    assert result.htf_directional_conflict is True
    assert payload["htf_directional_conflict"] is True
