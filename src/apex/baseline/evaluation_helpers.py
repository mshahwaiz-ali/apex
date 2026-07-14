"""Internal helpers for deterministic baseline campaign evaluation."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from apex.backtesting import HistoricalEdgeProfile
from apex.baseline.contracts import (
    BaselineEvaluationPolicy,
    BaselineReason,
    BaselineScenario,
    BaselineVerdict,
    CostSensitivityResult,
    StrategyBaselineAssessment,
)


def assess_strategy(
    strategy: str,
    baseline: BaselineScenario,
    scenarios: tuple[BaselineScenario, ...],
    policy: BaselineEvaluationPolicy,
) -> StrategyBaselineAssessment:
    profiles = profiles_for_strategy(baseline, strategy)
    sample_size = sum(profile.sample_size for profile in profiles)
    expectancy = weighted_metric(profiles, "expectancy")
    profit_factor = weighted_optional_metric(profiles, "profit_factor")
    maximum_drawdown = max(profile.maximum_drawdown_r for profile in profiles)
    symbols = tuple(sorted(dimension_values(profiles, "symbol") - {"unknown"}))
    regimes = tuple(sorted(dimension_values(profiles, "market_regime") - {"unknown"}))
    score_bands = score_band_expectancy(profiles)
    sensitivity = tuple(
        sensitivity_result(
            scenario,
            strategy,
            expectancy,
            policy.maximum_cost_expectancy_degradation,
        )
        for scenario in scenarios
    )

    reasons: list[BaselineReason] = []
    if sample_size < policy.minimum_strategy_trades:
        reasons.append(BaselineReason.SAMPLE_INSUFFICIENT)
    if expectancy <= 0.0:
        reasons.append(BaselineReason.EXPECTANCY_NOT_POSITIVE)
    if profit_factor is not None and profit_factor <= policy.minimum_profit_factor:
        reasons.append(BaselineReason.PROFIT_FACTOR_INADEQUATE)
    if maximum_drawdown > policy.maximum_drawdown_r:
        reasons.append(BaselineReason.DRAWDOWN_EXCESSIVE)
    if len(symbols) < policy.minimum_symbols:
        reasons.append(BaselineReason.SYMBOL_COVERAGE_INSUFFICIENT)
    if len(regimes) < policy.minimum_regimes:
        reasons.append(BaselineReason.REGIME_COVERAGE_INSUFFICIENT)
    if any(not item.stable for item in sensitivity):
        reasons.append(BaselineReason.COST_SENSITIVITY_EXCESSIVE)

    verdict = verdict_for(reasons)
    if not reasons:
        reasons.append(BaselineReason.BASELINE_ACCEPTED)
    return StrategyBaselineAssessment(
        strategy=strategy,
        verdict=verdict,
        sample_size=sample_size,
        expectancy=expectancy,
        profit_factor=profit_factor,
        maximum_drawdown_r=maximum_drawdown,
        symbols=symbols,
        regimes=regimes,
        score_bands=score_bands,
        cost_sensitivity=sensitivity,
        reasons=tuple(reasons),
    )


def verdict_for(reasons: Sequence[BaselineReason]) -> BaselineVerdict:
    if BaselineReason.SAMPLE_INSUFFICIENT in reasons:
        return BaselineVerdict.INSUFFICIENT_EVIDENCE
    hard = {
        BaselineReason.EXPECTANCY_NOT_POSITIVE,
        BaselineReason.PROFIT_FACTOR_INADEQUATE,
    }
    if any(reason in hard for reason in reasons):
        return BaselineVerdict.REJECT
    return BaselineVerdict.RESTRICT if reasons else BaselineVerdict.ACCEPT


def profiles_for_strategy(
    scenario: BaselineScenario,
    strategy: str,
) -> tuple[HistoricalEdgeProfile, ...]:
    return tuple(
        profile for profile in scenario.profiles if profile.dimensions.get("strategy") == strategy
    )


def weighted_metric(
    profiles: Sequence[HistoricalEdgeProfile],
    name: str,
) -> float:
    total = sum(profile.sample_size for profile in profiles)
    if name == "expectancy":
        numerator = sum(profile.expectancy * profile.sample_size for profile in profiles)
    else:
        raise ValueError(f"unsupported weighted metric: {name}")
    return numerator / total


def weighted_optional_metric(
    profiles: Sequence[HistoricalEdgeProfile],
    name: str,
) -> float | None:
    if name != "profit_factor":
        raise ValueError(f"unsupported optional metric: {name}")

    weighted_values: list[tuple[float, int]] = []

    for profile in profiles:
        profit_factor = profile.profit_factor
        if profit_factor is not None:
            weighted_values.append((profit_factor, profile.sample_size))

    if not weighted_values:
        return None

    total_sample_size = sum(sample_size for _, sample_size in weighted_values)
    weighted_total = sum(
        profit_factor * sample_size for profit_factor, sample_size in weighted_values
    )
    return weighted_total / total_sample_size


def dimension_values(
    profiles: Sequence[HistoricalEdgeProfile],
    name: str,
) -> set[str]:
    return {profile.dimensions.get(name, "unknown") for profile in profiles}


def score_band_expectancy(
    profiles: Sequence[HistoricalEdgeProfile],
) -> dict[str, float]:
    grouped: dict[str, list[HistoricalEdgeProfile]] = defaultdict(list)
    for profile in profiles:
        grouped[profile.dimensions.get("score_band", "unknown")].append(profile)
    return {key: weighted_metric(grouped[key], "expectancy") for key in sorted(grouped)}


def sensitivity_result(
    scenario: BaselineScenario,
    strategy: str,
    baseline_expectancy: float,
    maximum_degradation: float,
) -> CostSensitivityResult:
    profiles = profiles_for_strategy(scenario, strategy)
    expectancy = weighted_metric(profiles, "expectancy")
    degradation = None
    if baseline_expectancy > 0.0:
        degradation = (baseline_expectancy - expectancy) / baseline_expectancy
    stable = expectancy > 0.0 and (degradation is None or degradation <= maximum_degradation)
    return CostSensitivityResult(
        scenario_id=scenario.identifier,
        expectancy=expectancy,
        degradation_from_baseline=degradation,
        stable=stable,
    )


def assessment_payload(item: StrategyBaselineAssessment) -> dict[str, object]:
    return {
        "strategy": item.strategy,
        "verdict": item.verdict.value,
        "sample_size": item.sample_size,
        "expectancy": item.expectancy,
        "profit_factor": item.profit_factor,
        "maximum_drawdown_r": item.maximum_drawdown_r,
        "symbols": list(item.symbols),
        "regimes": list(item.regimes),
        "score_bands": dict(item.score_bands),
        "cost_sensitivity": [
            {
                "scenario_id": result.scenario_id,
                "expectancy": result.expectancy,
                "degradation_from_baseline": result.degradation_from_baseline,
                "stable": result.stable,
            }
            for result in item.cost_sensitivity
        ],
        "reasons": [reason.value for reason in item.reasons],
    }
