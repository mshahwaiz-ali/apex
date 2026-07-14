"""Validation and evaluation of completed frozen spot baseline campaigns."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence

from apex.spot_baseline.contracts import (
    SpotBaselineCampaignPlan,
    SpotBaselineEvaluationPolicy,
    SpotBaselineReason,
    SpotBaselineReport,
    SpotBaselineVerdict,
    SpotCampaignResult,
    SpotCostSensitivity,
    SpotStrategyAssessment,
)


def evaluate_spot_baseline_campaigns(
    plan: SpotBaselineCampaignPlan,
    results: Sequence[SpotCampaignResult],
    *,
    baseline_cost_variant_id: str,
    baseline_allocation_variant_id: str,
    policy: SpotBaselineEvaluationPolicy | None = None,
) -> SpotBaselineReport:
    """Validate a complete campaign matrix and freeze strategy verdicts."""
    resolved = policy or SpotBaselineEvaluationPolicy()
    result_map = _validate_results(plan, results)
    _require_variant(plan, baseline_cost_variant_id, baseline_allocation_variant_id)
    assessments = tuple(
        _assess_strategy(
            strategy,
            plan,
            result_map,
            baseline_cost_variant_id,
            baseline_allocation_variant_id,
            resolved,
        )
        for strategy in plan.strategies
    )
    payload = {
        "plan_id": plan.plan_id,
        "baseline_cost_variant_id": baseline_cost_variant_id,
        "baseline_allocation_variant_id": baseline_allocation_variant_id,
        "assessments": [_assessment_payload(item) for item in assessments],
    }
    report_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return SpotBaselineReport(
        plan_id=plan.plan_id,
        baseline_cost_variant_id=baseline_cost_variant_id,
        baseline_allocation_variant_id=baseline_allocation_variant_id,
        assessments=assessments,
        report_id=report_id,
    )


def spot_baseline_report_to_payload(report: SpotBaselineReport) -> dict[str, object]:
    """Convert a frozen report into a stable JSON-compatible payload."""
    return {
        "schema_version": 1,
        "report_id": report.report_id,
        "plan_id": report.plan_id,
        "baseline_cost_variant_id": report.baseline_cost_variant_id,
        "baseline_allocation_variant_id": report.baseline_allocation_variant_id,
        "assessments": [_assessment_payload(item) for item in report.assessments],
        "warnings": list(report.warnings),
    }


def _validate_results(
    plan: SpotBaselineCampaignPlan,
    results: Sequence[SpotCampaignResult],
) -> dict[str, SpotCampaignResult]:
    if not results:
        raise ValueError("spot baseline evaluation requires campaign results")
    result_map = {result.cell.key: result for result in results}
    if len(result_map) != len(results):
        raise ValueError("duplicate spot campaign cells are not allowed")
    planned_keys = {cell.key for cell in plan.cells}
    observed_keys = set(result_map)
    missing = planned_keys - observed_keys
    extra = observed_keys - planned_keys
    if missing:
        raise ValueError(f"missing spot campaign cells: {sorted(missing)}")
    if extra:
        raise ValueError(f"unplanned spot campaign cells: {sorted(extra)}")
    dataset_hashes = {dataset.dataset_id: dataset.content_hash for dataset in plan.datasets}
    for result in results:
        if result.plan_id != plan.plan_id:
            raise ValueError("spot campaign result plan drift detected")
        if result.assumptions_hash != plan.assumptions_hash:
            raise ValueError("spot campaign result assumptions drift detected")
        expected_hash = dataset_hashes[result.cell.dataset_id]
        if result.dataset_content_hash != expected_hash:
            raise ValueError("spot campaign result dataset drift detected")
        cost = next(
            variant
            for variant in plan.cost_variants
            if variant.identifier == result.cell.cost_variant_id
        )
        allocation = next(
            variant
            for variant in plan.allocation_variants
            if variant.identifier == result.cell.allocation_variant_id
        )
        config = result.backtest.config
        if config.fee_pct != cost.fee_pct or config.slippage_pct != cost.slippage_pct:
            raise ValueError("spot campaign result cost assumptions mismatch")
        if (
            config.maximum_allocation_per_position_pct
            != allocation.maximum_allocation_per_position_pct
            or config.maximum_total_exposure_pct
            != allocation.maximum_total_exposure_pct
            or config.maximum_concurrent_positions
            != allocation.maximum_concurrent_positions
        ):
            raise ValueError("spot campaign result allocation assumptions mismatch")
    return result_map


def _require_variant(
    plan: SpotBaselineCampaignPlan,
    cost_variant_id: str,
    allocation_variant_id: str,
) -> None:
    if cost_variant_id not in {item.identifier for item in plan.cost_variants}:
        raise ValueError("baseline cost variant is not present in the frozen plan")
    if allocation_variant_id not in {
        item.identifier for item in plan.allocation_variants
    }:
        raise ValueError("baseline allocation variant is not present in the frozen plan")


def _assess_strategy(
    strategy: str,
    plan: SpotBaselineCampaignPlan,
    result_map: dict[str, SpotCampaignResult],
    baseline_cost_id: str,
    baseline_allocation_id: str,
    policy: SpotBaselineEvaluationPolicy,
) -> SpotStrategyAssessment:
    baseline = tuple(
        result
        for result in result_map.values()
        if result.cell.strategy == strategy
        and result.cell.cost_variant_id == baseline_cost_id
        and result.cell.allocation_variant_id == baseline_allocation_id
    )
    trades = tuple(trade for result in baseline for trade in result.backtest.trades)
    sample_size = len(trades)
    expectancy = _average([trade.return_pct for trade in trades])
    gross_profit = sum(max(0.0, trade.net_pnl) for trade in trades)
    gross_loss = abs(sum(min(0.0, trade.net_pnl) for trade in trades))
    profit_factor = gross_profit / gross_loss if gross_loss > 0.0 else None
    maximum_drawdown = max(
        (result.backtest.metrics.maximum_drawdown_pct for result in baseline), default=0.0
    )
    total_return = _weighted_metric(baseline, "total_return_pct")
    symbols = tuple(sorted({trade.symbol for trade in trades}))
    regimes = tuple(sorted({trade.market_regime for trade in trades}))
    score_bands = _score_band_expectancy(trades)
    average_exposure = _weighted_metric(baseline, "average_exposure_pct")
    maximum_exposure = max(
        (result.backtest.metrics.maximum_exposure_pct for result in baseline), default=0.0
    )
    average_concurrent = _weighted_metric(baseline, "average_concurrent_positions")
    maximum_concurrent = max(
        (result.backtest.metrics.maximum_concurrent_positions for result in baseline),
        default=0,
    )
    sensitivity = tuple(
        _cost_sensitivity(
            strategy,
            cost.identifier,
            baseline_allocation_id,
            result_map,
            expectancy,
            policy.maximum_cost_expectancy_degradation,
        )
        for cost in plan.cost_variants
    )

    reasons: list[SpotBaselineReason] = []
    if sample_size < policy.minimum_strategy_trades:
        reasons.append(SpotBaselineReason.SAMPLE_INSUFFICIENT)
    if expectancy <= 0.0:
        reasons.append(SpotBaselineReason.EXPECTANCY_NOT_POSITIVE)
    if profit_factor is not None and profit_factor <= policy.minimum_profit_factor:
        reasons.append(SpotBaselineReason.PROFIT_FACTOR_INADEQUATE)
    if maximum_drawdown > policy.maximum_drawdown_pct:
        reasons.append(SpotBaselineReason.DRAWDOWN_EXCESSIVE)
    if len(symbols) < policy.minimum_symbols:
        reasons.append(SpotBaselineReason.SYMBOL_COVERAGE_INSUFFICIENT)
    if len(regimes) < policy.minimum_regimes:
        reasons.append(SpotBaselineReason.REGIME_COVERAGE_INSUFFICIENT)
    if any(not item.stable for item in sensitivity):
        reasons.append(SpotBaselineReason.COST_SENSITIVITY_EXCESSIVE)
    if average_exposure > policy.maximum_average_exposure_pct:
        reasons.append(SpotBaselineReason.EXPOSURE_EXCESSIVE)
    verdict = _verdict(reasons)
    if not reasons:
        reasons.append(SpotBaselineReason.BASELINE_ACCEPTED)
    return SpotStrategyAssessment(
        strategy=strategy,
        verdict=verdict,
        sample_size=sample_size,
        expectancy_pct=expectancy,
        profit_factor=profit_factor,
        maximum_drawdown_pct=maximum_drawdown,
        total_return_pct=total_return,
        symbols=symbols,
        regimes=regimes,
        score_bands=score_bands,
        average_exposure_pct=average_exposure,
        maximum_exposure_pct=maximum_exposure,
        average_concurrent_positions=average_concurrent,
        maximum_concurrent_positions=maximum_concurrent,
        cost_sensitivity=sensitivity,
        reasons=tuple(reasons),
    )


def _verdict(reasons: Sequence[SpotBaselineReason]) -> SpotBaselineVerdict:
    if SpotBaselineReason.SAMPLE_INSUFFICIENT in reasons:
        return SpotBaselineVerdict.INSUFFICIENT_EVIDENCE
    if any(
        reason
        in {
            SpotBaselineReason.EXPECTANCY_NOT_POSITIVE,
            SpotBaselineReason.PROFIT_FACTOR_INADEQUATE,
        }
        for reason in reasons
    ):
        return SpotBaselineVerdict.REJECT
    return SpotBaselineVerdict.RESTRICT if reasons else SpotBaselineVerdict.ACCEPT


def _cost_sensitivity(
    strategy: str,
    cost_id: str,
    allocation_id: str,
    result_map: dict[str, SpotCampaignResult],
    baseline_expectancy: float,
    maximum_degradation: float,
) -> SpotCostSensitivity:
    results = tuple(
        result
        for result in result_map.values()
        if result.cell.strategy == strategy
        and result.cell.cost_variant_id == cost_id
        and result.cell.allocation_variant_id == allocation_id
    )
    trades = tuple(trade for result in results for trade in result.backtest.trades)
    expectancy = _average([trade.return_pct for trade in trades])
    degradation = None
    if baseline_expectancy > 0.0:
        degradation = (baseline_expectancy - expectancy) / baseline_expectancy
    stable = expectancy > 0.0 and (
        degradation is None or degradation <= maximum_degradation
    )
    return SpotCostSensitivity(cost_id, expectancy, degradation, stable)


def _weighted_metric(
    results: Sequence[SpotCampaignResult], metric_name: str
) -> float:
    weights = [max(1, result.backtest.metrics.trade_count) for result in results]
    total = sum(weights)
    if total == 0:
        return 0.0
    return sum(
        float(getattr(result.backtest.metrics, metric_name)) * weight
        for result, weight in zip(results, weights, strict=True)
    ) / total


def _score_band_expectancy(trades: Sequence[object]) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for trade in trades:
        score_band = str(getattr(trade, "score_band"))
        grouped[score_band].append(float(getattr(trade, "return_pct")))
    return {key: _average(grouped[key]) for key in sorted(grouped)}


def _average(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _assessment_payload(item: SpotStrategyAssessment) -> dict[str, object]:
    return {
        "strategy": item.strategy,
        "verdict": item.verdict.value,
        "sample_size": item.sample_size,
        "expectancy_pct": item.expectancy_pct,
        "profit_factor": item.profit_factor,
        "maximum_drawdown_pct": item.maximum_drawdown_pct,
        "total_return_pct": item.total_return_pct,
        "symbols": list(item.symbols),
        "regimes": list(item.regimes),
        "score_bands": dict(item.score_bands),
        "average_exposure_pct": item.average_exposure_pct,
        "maximum_exposure_pct": item.maximum_exposure_pct,
        "average_concurrent_positions": item.average_concurrent_positions,
        "maximum_concurrent_positions": item.maximum_concurrent_positions,
        "cost_sensitivity": [
            {
                "cost_variant_id": value.cost_variant_id,
                "expectancy_pct": value.expectancy_pct,
                "degradation_from_baseline": value.degradation_from_baseline,
                "stable": value.stable,
            }
            for value in item.cost_sensitivity
        ],
        "reasons": [reason.value for reason in item.reasons],
    }
