"""Deterministic S3 spot strategy evaluators and routing."""

from __future__ import annotations

from collections.abc import Callable

from apex.config.spot_strategies import SpotStrategyConfig
from apex.domain.spot import SpotMarketRegime
from apex.domain.spot_strategy import (
    SpotStrategy,
    SpotStrategyCandidate,
    SpotStrategyDecision,
    SpotStrategyEligibility,
    SpotStrategyInput,
    SpotStrategyRoutingResult,
)
from apex.domain.spot_structure import SpotExtensionState, SpotTrendState

Evaluator = Callable[[SpotStrategyInput, SpotStrategyConfig], SpotStrategyCandidate]


def evaluate_higher_timeframe_trend_pullback(
    inputs: SpotStrategyInput,
    config: SpotStrategyConfig,
) -> SpotStrategyCandidate:
    reasons = _common_rejections(inputs)
    if inputs.structure_trend not in {
        SpotTrendState.UPTREND,
        SpotTrendState.STRONG_UPTREND,
    }:
        reasons.append("higher-timeframe trend is not bullish")
    if inputs.pullback_depth_percentage is None:
        reasons.append("pullback depth is unavailable")
    elif inputs.pullback_depth_percentage > config.maximum_pullback_depth_percentage:
        reasons.append("pullback is deeper than the configured limit")
    if not inputs.demand_lower <= inputs.current_price <= inputs.demand_upper:
        reasons.append("price is outside the higher-timeframe demand zone")
    decision = _decision(reasons, watch=inputs.structure_trend is SpotTrendState.UPTREND)
    return _candidate(
        SpotStrategy.HIGHER_TIMEFRAME_TREND_PULLBACK,
        decision,
        inputs,
        "bullish higher-timeframe structure is pulling back into demand",
        _buffered_invalidation(inputs.support_price, config),
        reasons,
        ("bullish structure", "planned pullback into demand"),
    )


def evaluate_breakout_retest(
    inputs: SpotStrategyInput,
    config: SpotStrategyConfig,
) -> SpotStrategyCandidate:
    reasons = _common_rejections(inputs)
    if not inputs.breakout_confirmed:
        reasons.append("breakout is not confirmed")
    if not inputs.retest_held:
        reasons.append("breakout retest has not held")
    if inputs.volume_ratio < config.breakout_volume_ratio:
        reasons.append("breakout volume is below the configured threshold")
    decision = _decision(reasons, watch=inputs.breakout_confirmed)
    return _candidate(
        SpotStrategy.BREAKOUT_RETEST,
        decision,
        inputs,
        "confirmed resistance breakout is holding as support on retest",
        _buffered_invalidation(inputs.resistance_price, config),
        reasons,
        ("breakout confirmed", "retest hold required"),
    )


def evaluate_accumulation_range_breakout(
    inputs: SpotStrategyInput,
    config: SpotStrategyConfig,
) -> SpotStrategyCandidate:
    reasons = _common_rejections(inputs)
    if not inputs.accumulation_confirmed:
        reasons.append("accumulation evidence is not confirmed")
    if not inputs.breakout_confirmed:
        reasons.append("range breakout is not confirmed")
    if inputs.range_width_percentage is None:
        reasons.append("range width is unavailable")
    elif inputs.range_width_percentage > config.maximum_accumulation_range_width_percentage:
        reasons.append("range is too wide to qualify as controlled accumulation")
    if inputs.volume_ratio < config.breakout_volume_ratio:
        reasons.append("range breakout volume is insufficient")
    decision = _decision(reasons, watch=inputs.accumulation_confirmed)
    return _candidate(
        SpotStrategy.ACCUMULATION_RANGE_BREAKOUT,
        decision,
        inputs,
        "controlled accumulation range is resolving upward with volume",
        _buffered_invalidation(inputs.support_price, config),
        reasons,
        ("accumulation confirmed", "upside range resolution"),
    )


def evaluate_liquidity_sweep_daily_recovery(
    inputs: SpotStrategyInput,
    config: SpotStrategyConfig,
) -> SpotStrategyCandidate:
    reasons = _common_rejections(inputs)
    if not inputs.liquidity_sweep_confirmed:
        reasons.append("downside liquidity sweep is not confirmed")
    if not inputs.daily_recovery_confirmed:
        reasons.append("daily recovery close is not confirmed")
    if inputs.volume_ratio < config.minimum_volume_ratio:
        reasons.append("recovery volume is below the configured threshold")
    decision = _decision(reasons, watch=inputs.liquidity_sweep_confirmed)
    return _candidate(
        SpotStrategy.LIQUIDITY_SWEEP_DAILY_RECOVERY,
        decision,
        inputs,
        "downside liquidity sweep has recovered on the daily structure",
        _buffered_invalidation(inputs.support_price, config),
        reasons,
        ("liquidity sweep", "daily recovery confirmation"),
    )


def evaluate_relative_strength_leader_pullback(
    inputs: SpotStrategyInput,
    config: SpotStrategyConfig,
) -> SpotStrategyCandidate:
    reasons = _common_rejections(inputs)
    if inputs.relative_strength_percentage is None:
        reasons.append("relative-strength value is unavailable")
    elif inputs.relative_strength_percentage < config.minimum_relative_strength_percentage:
        reasons.append("asset is not a configured relative-strength leader")
    if inputs.structure_trend not in {
        SpotTrendState.UPTREND,
        SpotTrendState.STRONG_UPTREND,
    }:
        reasons.append("relative-strength leader lacks bullish structure")
    if inputs.pullback_depth_percentage is None:
        reasons.append("leader pullback depth is unavailable")
    elif inputs.pullback_depth_percentage > config.maximum_pullback_depth_percentage:
        reasons.append("leader pullback is too deep")
    if not inputs.demand_lower <= inputs.current_price <= inputs.demand_upper:
        reasons.append("leader is not pulling back into demand")
    decision = _decision(reasons, watch=inputs.relative_strength_percentage is not None)
    return _candidate(
        SpotStrategy.RELATIVE_STRENGTH_LEADER_PULLBACK,
        decision,
        inputs,
        "relative-strength leader is pulling back into higher-timeframe demand",
        _buffered_invalidation(inputs.support_price, config),
        reasons,
        ("relative-strength leadership", "controlled demand-zone pullback"),
    )


def evaluate_post_capitulation_recovery(
    inputs: SpotStrategyInput,
    config: SpotStrategyConfig,
) -> SpotStrategyCandidate:
    reasons: list[str] = []
    if inputs.market_regime not in {
        SpotMarketRegime.CAPITULATION,
        SpotMarketRegime.RECOVERY,
    }:
        reasons.append("market is not in capitulation or recovery")
    if not inputs.capitulation_recovery_confirmed:
        reasons.append("post-capitulation recovery is not confirmed")
    if not inputs.daily_recovery_confirmed:
        reasons.append("daily recovery structure is not confirmed")
    if inputs.extension is SpotExtensionState.TERMINAL:
        reasons.append("asset remains terminally extended")
    decision = _decision(reasons, watch=inputs.market_regime is SpotMarketRegime.RECOVERY)
    return _candidate(
        SpotStrategy.POST_CAPITULATION_RECOVERY,
        decision,
        inputs,
        "broad capitulation is transitioning into a confirmed daily recovery",
        _buffered_invalidation(inputs.support_price, config),
        reasons,
        ("capitulation context", "daily recovery confirmation"),
        eligibility=SpotStrategyEligibility.PAPER_ONLY,
        warnings=("experimental strategy: paper-only until validated",),
    )


def evaluate_spot_strategies(
    inputs: SpotStrategyInput,
    *,
    config: SpotStrategyConfig | None = None,
) -> SpotStrategyRoutingResult:
    active = config or SpotStrategyConfig()
    evaluators: tuple[Evaluator, ...] = (
        evaluate_higher_timeframe_trend_pullback,
        evaluate_breakout_retest,
        evaluate_accumulation_range_breakout,
        evaluate_liquidity_sweep_daily_recovery,
        evaluate_relative_strength_leader_pullback,
        evaluate_post_capitulation_recovery,
    )
    candidates = tuple(evaluator(inputs, active) for evaluator in evaluators)
    selected = next(
        (item for item in candidates if item.decision is SpotStrategyDecision.APPROVE),
        None,
    )
    return SpotStrategyRoutingResult(selected=selected, candidates=candidates)


def _common_rejections(inputs: SpotStrategyInput) -> list[str]:
    reasons: list[str] = []
    if not inputs.allow_new_entries:
        reasons.append("broad-market regime blocks new entries")
    if inputs.market_regime in {SpotMarketRegime.RISK_OFF, SpotMarketRegime.CAPITULATION}:
        reasons.append("market regime is not eligible for standard spot entries")
    if inputs.extension is SpotExtensionState.TERMINAL:
        reasons.append("terminal extension blocks new entries")
    if inputs.extension is SpotExtensionState.DOWNSIDE_RISK:
        reasons.append("downside-risk state blocks new entries")
    return reasons


def _decision(reasons: list[str], *, watch: bool) -> SpotStrategyDecision:
    if not reasons:
        return SpotStrategyDecision.APPROVE
    return SpotStrategyDecision.WATCH if watch else SpotStrategyDecision.REJECT


def _buffered_invalidation(price: float, config: SpotStrategyConfig) -> float:
    return price * (1 - config.invalidation_buffer_percentage / 100)


def _candidate(
    strategy: SpotStrategy,
    decision: SpotStrategyDecision,
    inputs: SpotStrategyInput,
    thesis: str,
    invalidation_price: float,
    reasons: list[str],
    evidence: tuple[str, ...],
    *,
    eligibility: SpotStrategyEligibility = SpotStrategyEligibility.RESEARCH,
    warnings: tuple[str, ...] = (),
) -> SpotStrategyCandidate:
    return SpotStrategyCandidate(
        strategy=strategy,
        decision=decision,
        eligibility=eligibility,
        thesis=f"{inputs.symbol}: {thesis}",
        invalidation_price=invalidation_price,
        evidence=evidence,
        rejection_reasons=tuple(reasons),
        warnings=warnings,
    )
