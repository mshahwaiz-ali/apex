"""Deterministic coverage for V2 spot baseline planning and reports."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.spot_backtesting import (
    SpotBar,
    SpotEntryLeg,
    SpotMarketRegime,
    SpotOrderPlan,
    SpotTarget,
)
from apex.spot_baseline import (
    SpotAllocationVariant,
    SpotBaselineEvaluationPolicy,
    SpotBaselineVerdict,
    SpotCampaignInput,
    SpotCostVariant,
    SpotDatasetReference,
    SpotDatasetRole,
    build_spot_baseline_plan,
    evaluate_spot_baseline_campaigns,
    execute_spot_baseline_plan,
    list_spot_baseline_report_metadata_sqlite,
    load_spot_baseline_report_payload,
    load_spot_baseline_report_sqlite,
    write_spot_baseline_report,
    write_spot_baseline_report_sqlite,
)


START = datetime(2026, 1, 1, tzinfo=UTC)
STRATEGY = "higher_timeframe_trend_pullback"
SYMBOL = "BTCUSDT"


def _datasets() -> tuple[SpotDatasetReference, ...]:
    return (
        SpotDatasetReference("train", "hash-train", SpotDatasetRole.TRAIN, (SYMBOL,)),
        SpotDatasetReference(
            "validation", "hash-validation", SpotDatasetRole.VALIDATION, (SYMBOL,)
        ),
        SpotDatasetReference("test", "hash-test", SpotDatasetRole.TEST, (SYMBOL,)),
    )


def _plan():
    return build_spot_baseline_plan(
        strategies=(STRATEGY,),
        symbols=(SYMBOL,),
        datasets=_datasets(),
        cost_variants=(
            SpotCostVariant("baseline", 0.0, 0.0),
            SpotCostVariant("stress", 0.20, 0.20),
        ),
        allocation_variants=(SpotAllocationVariant("base", 20.0, 80.0, 4),),
        assumptions={"market_type": "SPOT", "long_only": True},
    )


def _campaign_input(cell_key: str) -> SpotCampaignInput:
    order = SpotOrderPlan(
        plan_id="order-" + cell_key,
        symbol=SYMBOL,
        strategy=STRATEGY,
        score_band="80-89",
        market_regime=SpotMarketRegime.RISK_ON,
        created_at=START,
        expires_at=START + timedelta(days=1),
        allocation_pct=20.0,
        entries=(SpotEntryLeg(100.0, 1.0, START),),
        targets=(SpotTarget(110.0, 1.0, "TP1"),),
        protective_stop=90.0,
    )
    bars = (
        SpotBar(SYMBOL, START, 100.0, 101.0, 99.0, 100.0, SpotMarketRegime.RISK_ON),
        SpotBar(
            SYMBOL,
            START + timedelta(days=1),
            105.0,
            111.0,
            104.0,
            110.0,
            SpotMarketRegime.RISK_ON,
        ),
    )
    return SpotCampaignInput((order,), bars)


def _completed():
    plan = _plan()
    inputs = {cell.key: _campaign_input(cell.key) for cell in plan.cells}
    results = execute_spot_baseline_plan(
        plan,
        inputs,
        starting_cash=10_000.0,
    )
    return plan, results


def test_plan_is_deterministic_and_requires_train_validation_test() -> None:
    assert _plan().plan_id == _plan().plan_id
    with pytest.raises(ValueError, match="missing roles"):
        build_spot_baseline_plan(
            strategies=(STRATEGY,),
            symbols=(SYMBOL,),
            datasets=(_datasets()[0],),
            cost_variants=(SpotCostVariant("baseline", 0.0, 0.0),),
            allocation_variants=(SpotAllocationVariant("base", 20.0, 80.0, 4),),
            assumptions={},
        )


def test_plan_rejects_missing_symbol_coverage_and_duplicate_variants() -> None:
    with pytest.raises(ValueError, match="missing symbols"):
        build_spot_baseline_plan(
            strategies=(STRATEGY,),
            symbols=(SYMBOL, "ETHUSDT"),
            datasets=_datasets(),
            cost_variants=(SpotCostVariant("baseline", 0.0, 0.0),),
            allocation_variants=(SpotAllocationVariant("base", 20.0, 80.0, 4),),
            assumptions={},
        )
    with pytest.raises(ValueError, match="cost variant ids"):
        build_spot_baseline_plan(
            strategies=(STRATEGY,),
            symbols=(SYMBOL,),
            datasets=_datasets(),
            cost_variants=(
                SpotCostVariant("same", 0.0, 0.0),
                SpotCostVariant("same", 0.1, 0.1),
            ),
            allocation_variants=(SpotAllocationVariant("base", 20.0, 80.0, 4),),
            assumptions={},
        )


def test_execution_rejects_missing_cells_and_mismatched_input() -> None:
    plan = _plan()
    inputs = {cell.key: _campaign_input(cell.key) for cell in plan.cells}
    inputs.pop(next(iter(inputs)))
    with pytest.raises(ValueError, match="missing spot campaign inputs"):
        execute_spot_baseline_plan(plan, inputs, starting_cash=10_000.0)

    complete = {cell.key: _campaign_input(cell.key) for cell in plan.cells}
    first = plan.cells[0]
    wrong_order = replace(complete[first.key].plans[0], symbol="ETHUSDT")
    complete[first.key] = replace(complete[first.key], plans=(wrong_order,))
    with pytest.raises(ValueError, match="symbol"):
        execute_spot_baseline_plan(plan, complete, starting_cash=10_000.0)


def test_evaluation_rejects_missing_duplicate_and_drifted_results() -> None:
    plan, results = _completed()
    with pytest.raises(ValueError, match="missing spot campaign cells"):
        evaluate_spot_baseline_campaigns(
            plan,
            results[:-1],
            baseline_cost_variant_id="baseline",
            baseline_allocation_variant_id="base",
        )
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_spot_baseline_campaigns(
            plan,
            results + (results[0],),
            baseline_cost_variant_id="baseline",
            baseline_allocation_variant_id="base",
        )
    drifted = (replace(results[0], plan_id="different"),) + results[1:]
    with pytest.raises(ValueError, match="plan drift"):
        evaluate_spot_baseline_campaigns(
            plan,
            drifted,
            baseline_cost_variant_id="baseline",
            baseline_allocation_variant_id="base",
        )


def test_report_contains_portfolio_metrics_cost_sensitivity_and_stable_id() -> None:
    plan, results = _completed()
    policy = SpotBaselineEvaluationPolicy(
        minimum_strategy_trades=1,
        minimum_symbols=1,
        minimum_regimes=1,
        maximum_drawdown_pct=50.0,
    )
    first = evaluate_spot_baseline_campaigns(
        plan,
        results,
        baseline_cost_variant_id="baseline",
        baseline_allocation_variant_id="base",
        policy=policy,
    )
    second = evaluate_spot_baseline_campaigns(
        plan,
        tuple(reversed(results)),
        baseline_cost_variant_id="baseline",
        baseline_allocation_variant_id="base",
        policy=policy,
    )
    assert first.report_id == second.report_id
    assessment = first.assessments[0]
    assert assessment.verdict is SpotBaselineVerdict.ACCEPT
    assert assessment.expectancy_pct > 0.0
    assert assessment.total_return_pct > 0.0
    assert assessment.maximum_drawdown_pct >= 0.0
    assert assessment.average_exposure_pct > 0.0
    assert assessment.score_bands["80-89"] > 0.0
    assert {item.cost_variant_id for item in assessment.cost_sensitivity} == {
        "baseline",
        "stress",
    }
    assert "historical spot results do not guarantee" in first.warnings[0]


def test_json_round_trip_and_sqlite_upsert_load(tmp_path: Path) -> None:
    plan, results = _completed()
    report = evaluate_spot_baseline_campaigns(
        plan,
        results,
        baseline_cost_variant_id="baseline",
        baseline_allocation_variant_id="base",
        policy=SpotBaselineEvaluationPolicy(
            minimum_strategy_trades=1,
            minimum_symbols=1,
            minimum_regimes=1,
        ),
    )
    json_path = tmp_path / "spot-baseline.json"
    write_spot_baseline_report(json_path, report)
    payload = load_spot_baseline_report_payload(json_path)
    assert payload["report_id"] == report.report_id

    database = tmp_path / "spot-baseline.sqlite3"
    write_spot_baseline_report_sqlite(database, report)
    write_spot_baseline_report_sqlite(database, report)
    stored = load_spot_baseline_report_sqlite(database, report.report_id)
    assert stored == payload
    assert list_spot_baseline_report_metadata_sqlite(database) == (
        {"report_id": report.report_id, "plan_id": report.plan_id},
    )
