from __future__ import annotations

import pytest

from apex.application.methodology_contracts import (
    ConfidenceAssessment,
    ConfidenceBasis,
    ConfidenceLabel,
    EntryOpportunity,
    EntryOpportunityType,
    EvidenceEffect,
    EvidenceFamily,
    EvidenceObservation,
    RejectionCode,
    RejectionReason,
    RejectionSeverity,
)
from apex.application.methodology_strategy_contracts import (
    ConfirmationPolicy,
    MarketStateClassification,
    PrimaryMarketState,
    SecondaryMarketCondition,
    StrategyEligibility,
)


def test_evidence_observation_requires_normalized_values() -> None:
    observation = EvidenceObservation(
        family=EvidenceFamily.STRUCTURE,
        source="swing_sequence",
        normalized_strength=0.8,
        freshness=1.0,
        independence_group="price_structure",
        effect=EvidenceEffect.SUPPORTS,
        reason="higher highs and higher lows remain intact",
    )

    assert observation.family is EvidenceFamily.STRUCTURE

    with pytest.raises(ValueError, match="between zero and one"):
        EvidenceObservation(
            family=EvidenceFamily.MOMENTUM,
            source="rsi",
            normalized_strength=1.1,
            freshness=1.0,
            independence_group="momentum_oscillator",
            effect=EvidenceEffect.SUPPORTS,
            reason="invalid strength",
        )


def test_entry_opportunity_validates_zone_and_expiry() -> None:
    entry = EntryOpportunity(
        kind=EntryOpportunityType.RETEST,
        zone_low=99.0,
        zone_high=101.0,
        ideal_entry=100.0,
        confirmation_level=101.5,
        maximum_chase=102.0,
        current_distance_percentage=0.4,
        current_distance_atr=0.2,
        quality=0.75,
        reason="breakout retest remains close to structure",
        expiry_bars=4,
    )

    assert entry.ideal_entry == 100.0

    with pytest.raises(ValueError, match="inside the entry zone"):
        EntryOpportunity(
            kind=EntryOpportunityType.IMMEDIATE,
            zone_low=99.0,
            zone_high=101.0,
            ideal_entry=102.0,
            confirmation_level=None,
            maximum_chase=103.0,
            current_distance_percentage=0.0,
            current_distance_atr=0.0,
            quality=0.5,
            reason="invalid geometry",
            expiry_bars=1,
        )


def test_calibrated_confidence_requires_success_rate_and_sample() -> None:
    confidence = ConfidenceAssessment(
        setup=ConfidenceLabel.HIGH,
        execution=ConfidenceLabel.MODERATE,
        target=ConfidenceLabel.MODERATE,
        data=ConfidenceLabel.HIGH,
        historical=ConfidenceLabel.MODERATE,
        overall=ConfidenceLabel.MODERATE,
        basis=ConfidenceBasis.HISTORICALLY_CALIBRATED,
        strongest_support="structure and participation align",
        strongest_contradiction=None,
        model_estimated_success_rate=0.58,
        sample_size=240,
    )

    assert confidence.sample_size == 240

    with pytest.raises(ValueError, match="historically calibrated"):
        ConfidenceAssessment(
            setup=ConfidenceLabel.MODERATE,
            execution=ConfidenceLabel.MODERATE,
            target=ConfidenceLabel.MODERATE,
            data=ConfidenceLabel.MODERATE,
            historical=ConfidenceLabel.LOW,
            overall=ConfidenceLabel.MODERATE,
            basis=ConfidenceBasis.RULE_BASED,
            strongest_support="rule-based setup quality",
            strongest_contradiction=None,
            model_estimated_success_rate=0.55,
            sample_size=100,
        )


def test_hard_blockers_are_gates_not_penalties() -> None:
    blocker = RejectionReason(
        code=RejectionCode.NO_DEFINABLE_INVALIDATION,
        severity=RejectionSeverity.HARD_BLOCKER,
        reason="the thesis has no structural failure level",
    )

    assert blocker.penalty == 0.0

    with pytest.raises(ValueError, match="cannot carry score penalties"):
        RejectionReason(
            code=RejectionCode.NO_DEFINABLE_INVALIDATION,
            severity=RejectionSeverity.HARD_BLOCKER,
            reason="invalid blocker representation",
            penalty=0.2,
        )


def test_market_state_and_strategy_taxonomy_are_explicit() -> None:
    state = MarketStateClassification(
        primary=PrimaryMarketState.PULLBACK_IN_UPTREND,
        secondary=(SecondaryMarketCondition.VOLATILITY_CONTRACTION,),
        evidence_ids=("structure:hh_hl", "volatility:atr_contracting"),
        reason="trend structure is intact while the pullback contracts",
    )
    eligibility = StrategyEligibility(
        strategy_id="trend_pullback",
        strategy_version="1",
        compatible_states=(PrimaryMarketState.PULLBACK_IN_UPTREND,),
        prohibited_states=(PrimaryMarketState.CHAOTIC,),
        mandatory_evidence=(EvidenceFamily.STRUCTURE, EvidenceFamily.TREND),
        optional_evidence=(EvidenceFamily.PARTICIPATION,),
        confirmation_policy=ConfirmationPolicy.LOWER_TIMEFRAME_CONFIRMATION_ALLOWED,
        entry_models=("preferred_nearby_entry", "reclaim_entry"),
        invalidation_method="swing_and_zone_invalidation",
        target_methods=("prior_swing", "structural_obstacle"),
        expiry_policy="expire_after_setup_structure_changes",
        historical_segment_key="trend_pullback:v1",
    )

    assert state.primary is PrimaryMarketState.PULLBACK_IN_UPTREND
    assert eligibility.strategy_id == "trend_pullback"
