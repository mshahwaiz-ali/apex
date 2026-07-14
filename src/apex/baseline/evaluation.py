"""Deterministic evaluation of frozen baseline campaign scenarios."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence
from statistics import fmean

from apex.application.baseline_campaign_plan import BaselineCampaignPlan
from apex.backtesting import HistoricalEdgeProfile
from apex.baseline.contracts import (
    BaselineEvaluationPolicy,
    BaselineEvaluationReport,
    BaselineReason,
    BaselineScenario,
    BaselineVerdict,
    CostSensitivityResult,
    StrategyBaselineAssessment,
)


def evaluate_baseline_campaigns(
    plan: BaselineCampaignPlan,
    scenarios: Sequence[BaselineScenario],
    *,
    baseline_scenario_id: str,
    policy: BaselineEvaluationPolicy | None = None,
) -> BaselineEvaluationReport:
    """Evaluate real campaign profiles against one frozen plan."""

    resolved_policy = policy or BaselineEvaluationPolicy()
    scenario_map = _validate_scenarios(plan, scenarios, baseline_scenario_id)
    baseline = scenario_map[baseline_scenario_id]
    strategies = tuple(strategy.value for strategy in plan.strategies)
    assessments = tuple(
        _assess_strategy(
            strategy,
            baseline,
            tuple(scenario_map[key] for key in sorted(scenario_map)),
            resolved_policy,
        )
        for strategy in sorted(strategies)
    )
    payload = {
        "plan_id": plan.plan_id,
        "baseline_scenario_id": baseline_scenario_id,
        "scenario_ids": sorted(scenario_map),
        "assessments": [_assessment_payload(item) for item in assessments],
    }
    report_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return BaselineEvaluationReport(
        plan_id=plan.plan_id,
        baseline_scenario_id=baseline_scenario_id,
        scenario_ids=tuple(sorted(scenario_map)),
        assessments=assessments,
        report_id=report_id,
        warnings=(
            "baseline verdicts are historical research outputs, not profitability guarantees",
            "out-of-sample and forward-paper validation remain separate gates",
        ),
    )


def baseline_report_to_payload(report: BaselineEvaluationReport) -> dict[str, object]:
    return {
        "schema_version": 1,
        "report_id": report.report_id,
        "plan_id": report.plan_id,
        "baseline_scenario_id": report.baseline_scenario_id,
        "scenario_ids": list(report.scenario_ids),
        "assessments": [_assessment_payload(item) for item in report.assessments],
        "warnings": list(report.warnings),
    }


def _validate_scenarios(
    plan: BaselineCampaignPlan,
    scenarios: Sequence[BaselineScenario],
    baseline_scenario_id: str,
) -> dict[str, BaselineScenario]:
    if not scenarios:
        raise ValueError("baseline evaluation requires at least one scenario")
    scenario_map = {scenario.identifier: scenario for scenario in scenarios}
    if len(scenario_map) != len(scenarios):
        raise ValueError("baseline scenario identifiers must be unique")
    if baseline_scenario_id not in scenario_map:
        raise ValueError("baseline scenario id must refer to a supplied scenario")
    planned = {strategy.value for strategy in plan.strategies}
    for scenario in scenarios:
        observed = {
            profile.dimensions.get("strategy", "unknown") for profile in scenario.profiles
        }
        missing = planned - observed
        if missing:
            raise ValueError(
                f"scenario {scenario.identifier} is missing planned strategies: {sorted(missing)}"
            )
    return scenario_map


def _assess_strategy(
    strategy: str,
    baseline: BaselineScenario,
    scenarios: tuple[BaselineScenario, ...],
    policy: BaselineEvaluationPolicy,
) -> StrategyBaselineAssessment:
    profiles = _profiles_for_strategy(baseline, strategy)
    sample_size = sum(profile.sample_size for profile in profiles)
    expectancy = _weighted_metric(profiles, "expectancy")
    profit_factor = _weighted_optional_metric(profiles, "profit_factor")
    maximum_drawdown = max(profile.maximum_drawdown_r for profile in profiles)
    symbols = tuple(sorted(_dimension_values(profiles, "symbol") - {"unknown"}))
    regimes = tuple(sorted(_dimension_values(profiles, "market_regime") - {"unknown"}))
    score_bands = _score_band_expectancy(profiles)
    sensitivity = tuple(
        _sensitivity_result(
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

    verdict = _verdict(reasons)
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


def _verdict(reasons: Sequence[BaselineReason]) -> BaselineVerdict:
    if BaselineReason.SAMPLE_INSUFFICIENT in reasons:
        return BaselineVerdict.INSUFFICIENT_EVIDENCE
    hard = {
        BaselineReason.EXPECTANCY_NOT_POSITIVE,
        BaselineReason.PROFIT_FACTOR_INADEQUATE,
    }
    if any(reason in hard for reason in reasons):
        return BaselineVerdict.REJECT
    return BaselineVerdict.RESTRICT if reasons else BaselineVerdict.ACCEPT


def _profiles_for_strategy(
    scenario: BaselineScenario,
    strategy: str,
) -> tuple[HistoricalEdgeProfile, ...]:
    return tuple(
        profile
        for profile in scenario.profiles
        if profile.dimensions.get("strategy") == strategy
    )


def _weighted_metric(profiles: Sequence[HistoricalEdgeProfile], name: str) -> float:
    total = sum(profile.sample_size for profile in profiles)
    return sum(getattr(profile, name) * profile.sample_size for profile in profiles) / total


def _weighted_optional_metric(
    profiles: Sequence[HistoricalEdgeProfile],
    name: str,
) -> float | None:
    available = tuple(profile for profile in profiles if getattr(profile, name) is not None)
    if not available:
        return None
    total = sum(profile.sample_size for profile in available)
    return sum(float(getattr(profile, name)) * profile.sample_size for profile in available) / total


def _dimension_values(profiles: Sequence[HistoricalEdgeProfile], name: str) -> set[str]:
    return {profile.dimensions.get(name, "unknown") for profile in profiles}


def _score_band_expectancy(
    profiles: Sequence[HistoricalEdgeProfile],
) -> dict[str, float]:
    grouped: dict[str, list[HistoricalEdgeProfile]] = defaultdict(list)
    for profile in profiles:
        grouped[profile.dimensions.get("score_band", "unknown")].append(profile)
    return {key: _weighted_metric(grouped[key], "expectancy") for key in sorted(grouped)}


def _sensitivity_result(
    scenario: BaselineScenario,
    strategy: str,
    baseline_expectancy: float,
    maximum_degradation: float,
) -> CostSensitivityResult:
    profiles = _profiles_for_strategy(scenario, strategy)
    expectancy = _weighted_metric(profiles, "expectancy")
    degradation = None
    if baseline_expectancy > 0.0:
        degradation = (baseline_expectancy - expectancy) / baseline_expectancy
    stable = expectancy > 0.0 and (
        degradation is None or degradation <= maximum_degradation
    )
    return CostSensitivityResult(
        scenario_id=scenario.identifier,
        expectancy=expectancy,
        degradation_from_baseline=degradation,
        stable=stable,
    )


def _assessment_payload(item: StrategyBaselineAssessment) -> dict[str, object]:
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
