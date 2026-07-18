"""Canonical methodology declarations for every Apex strategy family."""

from __future__ import annotations

from apex.application.methodology_contracts import EvidenceFamily
from apex.application.methodology_strategy_contracts import (
    ConfirmationPolicy,
    PrimaryMarketState,
    StrategyEligibility,
)
from apex.strategies.strategy_types import StrategyType

_CHAOTIC = (PrimaryMarketState.CHAOTIC,)


def _eligibility(
    strategy: StrategyType,
    states: tuple[PrimaryMarketState, ...],
    mandatory: tuple[EvidenceFamily, ...],
    optional: tuple[EvidenceFamily, ...],
    confirmation: ConfirmationPolicy,
    entries: tuple[str, ...],
    targets: tuple[str, ...],
) -> StrategyEligibility:
    return StrategyEligibility(
        strategy_id=strategy.value,
        strategy_version="1",
        compatible_states=states,
        prohibited_states=_CHAOTIC,
        mandatory_evidence=mandatory,
        optional_evidence=optional,
        confirmation_policy=confirmation,
        entry_models=entries,
        invalidation_method="structural_failure_with_volatility_buffer",
        target_methods=targets,
        expiry_policy="expire_on_structure_change_or_configured_bar_limit",
        historical_segment_key=f"{strategy.value}:v1",
    )


METHODOLOGY_STRATEGY_REGISTRY: dict[StrategyType, StrategyEligibility] = {
    StrategyType.MOMENTUM_BREAKOUT: _eligibility(
        StrategyType.MOMENTUM_BREAKOUT,
        (PrimaryMarketState.BREAKOUT_ATTEMPT, PrimaryMarketState.POST_BREAKOUT),
        (EvidenceFamily.STRUCTURE, EvidenceFamily.PARTICIPATION),
        (EvidenceFamily.MOMENTUM, EvidenceFamily.VOLATILITY),
        ConfirmationPolicy.CLOSE_REQUIRED,
        ("immediate_entry", "retest_entry"),
        ("measured_move", "structural_obstacle"),
    ),
    StrategyType.BREAKOUT_CONTINUATION: _eligibility(
        StrategyType.BREAKOUT_CONTINUATION,
        (PrimaryMarketState.POST_BREAKOUT, PrimaryMarketState.POST_BREAKDOWN),
        (EvidenceFamily.STRUCTURE, EvidenceFamily.TREND),
        (EvidenceFamily.PARTICIPATION, EvidenceFamily.MOMENTUM),
        ConfirmationPolicy.MIXED,
        ("preferred_nearby_entry", "pullback_entry"),
        ("measured_move", "prior_swing", "structural_obstacle"),
    ),
    StrategyType.BREAKOUT_RETEST: _eligibility(
        StrategyType.BREAKOUT_RETEST,
        (PrimaryMarketState.POST_BREAKOUT, PrimaryMarketState.POST_BREAKDOWN),
        (EvidenceFamily.STRUCTURE, EvidenceFamily.LIQUIDITY),
        (EvidenceFamily.PARTICIPATION, EvidenceFamily.CANDLE),
        ConfirmationPolicy.RETEST_REQUIRED,
        ("retest_entry",),
        ("prior_swing", "measured_move"),
    ),
    StrategyType.FIRST_PULLBACK_CONTINUATION: _eligibility(
        StrategyType.FIRST_PULLBACK_CONTINUATION,
        (PrimaryMarketState.PULLBACK_IN_UPTREND, PrimaryMarketState.RALLY_IN_DOWNTREND),
        (EvidenceFamily.STRUCTURE, EvidenceFamily.TREND),
        (EvidenceFamily.PARTICIPATION, EvidenceFamily.MOMENTUM),
        ConfirmationPolicy.LOWER_TIMEFRAME_CONFIRMATION_ALLOWED,
        ("pullback_entry", "reclaim_entry"),
        ("prior_swing", "trend_projection"),
    ),
    StrategyType.TREND_PULLBACK: _eligibility(
        StrategyType.TREND_PULLBACK,
        (PrimaryMarketState.PULLBACK_IN_UPTREND, PrimaryMarketState.RALLY_IN_DOWNTREND),
        (EvidenceFamily.STRUCTURE, EvidenceFamily.TREND),
        (EvidenceFamily.MOMENTUM, EvidenceFamily.PARTICIPATION),
        ConfirmationPolicy.LOWER_TIMEFRAME_CONFIRMATION_ALLOWED,
        ("preferred_nearby_entry", "reclaim_entry"),
        ("prior_swing", "structural_obstacle"),
    ),
    StrategyType.COMPRESSION_EXPANSION: _eligibility(
        StrategyType.COMPRESSION_EXPANSION,
        (PrimaryMarketState.COMPRESSING, PrimaryMarketState.BREAKOUT_ATTEMPT, PrimaryMarketState.BREAKDOWN_ATTEMPT),
        (EvidenceFamily.STRUCTURE, EvidenceFamily.VOLATILITY),
        (EvidenceFamily.PARTICIPATION, EvidenceFamily.MOMENTUM),
        ConfirmationPolicy.CLOSE_REQUIRED,
        ("retest_entry", "aggressive_entry"),
        ("compression_projection", "structural_obstacle"),
    ),
    StrategyType.RANGE_REVERSAL: _eligibility(
        StrategyType.RANGE_REVERSAL,
        (PrimaryMarketState.RANGING,),
        (EvidenceFamily.STRUCTURE, EvidenceFamily.LIQUIDITY),
        (EvidenceFamily.CANDLE, EvidenceFamily.MOMENTUM),
        ConfirmationPolicy.REJECTION_REQUIRED if hasattr(ConfirmationPolicy, "REJECTION_REQUIRED") else ConfirmationPolicy.MIXED,
        ("rejection_entry", "reclaim_entry"),
        ("range_midpoint", "opposite_range_boundary"),
    ),
    StrategyType.FAILED_BREAKOUT_REVERSAL: _eligibility(
        StrategyType.FAILED_BREAKOUT_REVERSAL,
        (PrimaryMarketState.REVERSAL_ATTEMPT_UP, PrimaryMarketState.REVERSAL_ATTEMPT_DOWN, PrimaryMarketState.TRANSITIONAL),
        (EvidenceFamily.STRUCTURE, EvidenceFamily.LIQUIDITY),
        (EvidenceFamily.CANDLE, EvidenceFamily.PARTICIPATION),
        ConfirmationPolicy.RECLAIM_REQUIRED,
        ("reclaim_entry", "rejection_entry"),
        ("range_midpoint", "opposite_structure"),
    ),
    StrategyType.LIQUIDITY_REJECTION_REVERSAL: _eligibility(
        StrategyType.LIQUIDITY_REJECTION_REVERSAL,
        (PrimaryMarketState.RANGING, PrimaryMarketState.REVERSAL_ATTEMPT_UP, PrimaryMarketState.REVERSAL_ATTEMPT_DOWN),
        (EvidenceFamily.LIQUIDITY, EvidenceFamily.STRUCTURE),
        (EvidenceFamily.CANDLE, EvidenceFamily.PARTICIPATION),
        ConfirmationPolicy.RECLAIM_REQUIRED,
        ("rejection_entry", "reclaim_entry"),
        ("range_midpoint", "opposite_liquidity_pool"),
    ),
    StrategyType.VWAP_RECLAIM_REJECTION: _eligibility(
        StrategyType.VWAP_RECLAIM_REJECTION,
        (PrimaryMarketState.TRENDING_UP, PrimaryMarketState.TRENDING_DOWN, PrimaryMarketState.TRANSITIONAL),
        (EvidenceFamily.STRUCTURE, EvidenceFamily.TREND),
        (EvidenceFamily.PARTICIPATION, EvidenceFamily.MOMENTUM),
        ConfirmationPolicy.RECLAIM_REQUIRED,
        ("reclaim_entry", "rejection_entry"),
        ("prior_swing", "structural_obstacle"),
    ),
    StrategyType.MOMENTUM_SCALP: _eligibility(
        StrategyType.MOMENTUM_SCALP,
        (PrimaryMarketState.TRENDING_UP, PrimaryMarketState.TRENDING_DOWN, PrimaryMarketState.POST_BREAKOUT, PrimaryMarketState.POST_BREAKDOWN),
        (EvidenceFamily.MOMENTUM, EvidenceFamily.PARTICIPATION),
        (EvidenceFamily.STRUCTURE, EvidenceFamily.VOLATILITY),
        ConfirmationPolicy.INTRABAR_ALLOWED,
        ("aggressive_entry", "immediate_entry"),
        ("nearby_liquidity", "short_measured_move"),
    ),
    StrategyType.EXHAUSTION_REVERSAL: _eligibility(
        StrategyType.EXHAUSTION_REVERSAL,
        (PrimaryMarketState.EXHAUSTED_UP, PrimaryMarketState.EXHAUSTED_DOWN),
        (EvidenceFamily.STRUCTURE, EvidenceFamily.MOMENTUM),
        (EvidenceFamily.CANDLE, EvidenceFamily.PARTICIPATION, EvidenceFamily.DERIVATIVES),
        ConfirmationPolicy.CLOSE_REQUIRED,
        ("rejection_entry", "reclaim_entry"),
        ("mean_reversion_level", "prior_structure"),
    ),
}


def strategy_eligibility(strategy: StrategyType) -> StrategyEligibility:
    return METHODOLOGY_STRATEGY_REGISTRY[strategy]


def strategy_registry_payload() -> dict[str, dict[str, object]]:
    return {
        strategy.value: {
            "strategy_version": item.strategy_version,
            "compatible_states": [state.value for state in item.compatible_states],
            "prohibited_states": [state.value for state in item.prohibited_states],
            "mandatory_evidence": [family.value for family in item.mandatory_evidence],
            "optional_evidence": [family.value for family in item.optional_evidence],
            "confirmation_policy": item.confirmation_policy.value,
            "entry_models": list(item.entry_models),
            "invalidation_method": item.invalidation_method,
            "target_methods": list(item.target_methods),
            "expiry_policy": item.expiry_policy,
            "historical_segment_key": item.historical_segment_key,
        }
        for strategy, item in METHODOLOGY_STRATEGY_REGISTRY.items()
    }


__all__ = [
    "METHODOLOGY_STRATEGY_REGISTRY",
    "strategy_eligibility",
    "strategy_registry_payload",
]
