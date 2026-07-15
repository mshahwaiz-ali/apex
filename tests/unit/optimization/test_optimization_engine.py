import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apex.backtesting import (
    BacktestConfig,
    BacktestRequest,
    BacktestSignal,
    HistoricalBacktestRunner,
)
from apex.domain import Candle
from apex.optimization import (
    CalibrationEvaluation,
    CandidateParameterSet,
    OptimizationDecision,
    OptimizationGroup,
    OptimizationRunConfig,
    PerformanceSummary,
    WalkForwardSplit,
    calibration_to_payload,
    compare_backtest_studies,
    compare_performance,
    evaluate_walk_forward_calibration,
    load_performance_report,
    performance_from_backtest_study,
    performance_from_campaign_payload,
    save_optimization_result,
)
from apex.strategies import StrategyType, TradeDirection


def _summary(
    *,
    trades: int = 20,
    win_rate: float = 0.45,
    expectancy: float = 10.0,
    profit_factor: float | None = 1.4,
    drawdown: float = 100.0,
) -> PerformanceSummary:
    return PerformanceSummary(
        total_trades=trades,
        win_rate=win_rate,
        expectancy=expectancy,
        profit_factor=profit_factor,
        maximum_drawdown=drawdown,
        net_profit=trades * expectancy,
        by_symbol={"BTC/USDT": trades},
        by_strategy={"trend_pullback": trades},
        by_regime={"trend": trades},
        by_score_band={"70-80": trades},
    )


def _signal(generated_at: datetime) -> BacktestSignal:
    return BacktestSignal(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=generated_at,
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        quantity=10.0,
        risk_amount=20.0,
        confidence_score=80.0,
    )


def _candle(index: int, *, high: float, low: float, close: float) -> Candle:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    return Candle(
        symbol="BTC/USDT",
        timeframe="5m",
        open_time=now + timedelta(minutes=5 * index),
        close_time=now + timedelta(minutes=5 * (index + 1)),
        open=100.0,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        is_closed=True,
        source="fixture",
    )


def test_candidate_is_accepted_when_metrics_preserve_baseline() -> None:
    result = compare_performance(
        _summary(),
        _summary(expectancy=12.0, profit_factor=1.5, drawdown=95.0),
        run_config=OptimizationRunConfig(
            identifier="test",
            variable_group=OptimizationGroup.SCORING_THRESHOLDS,
            maximum_symbol_trade_share=1.0,
        ),
        parameter_set=CandidateParameterSet(
            identifier="candidate",
            group=OptimizationGroup.SCORING_THRESHOLDS,
            parameters={"minimum_score": 70.0},
        ),
    )

    assert result.decision is OptimizationDecision.ACCEPTED
    assert result.recommended_patch == {"scoring_thresholds": {"minimum_score": 70.0}}


def test_win_rate_only_improvement_is_rejected() -> None:
    result = compare_performance(
        _summary(win_rate=0.4, expectancy=10.0),
        _summary(win_rate=0.6, expectancy=8.0, profit_factor=1.3),
        run_config=OptimizationRunConfig(
            identifier="test",
            variable_group=OptimizationGroup.RISK_THRESHOLDS,
            require_profit_factor_not_worse=False,
        ),
        parameter_set=CandidateParameterSet(
            identifier="candidate",
            group=OptimizationGroup.RISK_THRESHOLDS,
            parameters={"maximum_stop_distance_pct": 2.5},
        ),
    )

    assert result.decision is OptimizationDecision.REJECTED
    assert "win rate" in " ".join(result.reasons)


def test_symbol_dependency_is_rejected() -> None:
    result = compare_performance(
        _summary(trades=20, expectancy=10.0),
        _summary(trades=20, expectancy=12.0, profit_factor=1.6),
        run_config=OptimizationRunConfig(
            identifier="test",
            variable_group=OptimizationGroup.SYMBOL_FILTERS,
            maximum_symbol_trade_share=0.5,
        ),
        parameter_set=CandidateParameterSet(
            identifier="candidate",
            group=OptimizationGroup.SYMBOL_FILTERS,
            parameters={"symbols": "BTC/USDT"},
        ),
    )

    assert result.decision is OptimizationDecision.REJECTED
    assert "dependent on one symbol" in " ".join(result.reasons)


def test_optimization_consumes_backtest_studies() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    baseline = HistoricalBacktestRunner().run(
        BacktestRequest(
            signals=(_signal(now),),
            candles_by_symbol={"BTC/USDT": (_candle(0, high=105.0, low=99.0, close=104.0),)},
            config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
            dataset_id="baseline",
        )
    )
    candidate = HistoricalBacktestRunner().run(
        BacktestRequest(
            signals=(_signal(now),),
            candles_by_symbol={"BTC/USDT": (_candle(0, high=105.0, low=99.0, close=104.0),)},
            config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
            dataset_id="candidate",
        )
    )

    summary = performance_from_backtest_study(candidate)
    result = compare_backtest_studies(
        baseline,
        candidate,
        run_config=OptimizationRunConfig(
            identifier="test",
            variable_group=OptimizationGroup.SCORING_THRESHOLDS,
            minimum_trades=1,
            maximum_symbol_trade_share=1.0,
        ),
        parameter_set=CandidateParameterSet(
            identifier="candidate",
            group=OptimizationGroup.SCORING_THRESHOLDS,
            parameters={"minimum_score": 60.0},
        ),
    )

    assert summary.total_trades == 1
    assert result.decision is OptimizationDecision.ACCEPTED


def test_report_round_trip_does_not_mutate_config(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "metrics": {
                    "total_trades": 3,
                    "win_rate": 0.5,
                    "expectancy": 2.0,
                    "profit_factor": 1.2,
                    "maximum_drawdown": 5.0,
                    "net_profit": 6.0,
                    "by_symbol": {"BTC/USDT": 3},
                }
            }
        ),
        encoding="utf-8",
    )

    summary = load_performance_report(report)
    result = compare_performance(
        _summary(),
        summary,
        run_config=OptimizationRunConfig(
            identifier="test",
            variable_group=OptimizationGroup.SYMBOL_FILTERS,
        ),
        parameter_set=CandidateParameterSet(
            identifier="candidate",
            group=OptimizationGroup.SYMBOL_FILTERS,
            parameters={"symbols": "BTC/USDT"},
        ),
    )
    output = tmp_path / "optimization.json"
    save_optimization_result(result, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["run_config"]["variable_group"] == "symbol_filters"
    assert payload["recommended_patch"] == {}


def test_campaign_payload_aggregates_selected_best_variant_across_symbols() -> None:
    payload = {
        "best_variant_id": "candidate",
        "variants": [
            {
                "symbol": "BTC/USDT",
                "variant": {"identifier": "baseline"},
                "metrics": {
                    "total_trades": 2,
                    "win_rate": 0.5,
                    "gross_profit": 8.0,
                    "gross_loss": -2.0,
                    "net_profit": 6.0,
                    "maximum_drawdown": 1.0,
                    "by_strategy": {"trend_pullback": 2},
                },
            },
            {
                "symbol": "BTC/USDT",
                "variant": {"identifier": "candidate"},
                "metrics": {
                    "total_trades": 2,
                    "win_rate": 0.5,
                    "gross_profit": 10.0,
                    "gross_loss": -2.0,
                    "net_profit": 8.0,
                    "maximum_drawdown": 1.0,
                    "by_strategy": {"trend_pullback": 2},
                },
            },
            {
                "symbol": "ETH/USDT",
                "variant": {"identifier": "candidate"},
                "metrics": {
                    "total_trades": 3,
                    "win_rate": 2 / 3,
                    "gross_profit": 12.0,
                    "gross_loss": -3.0,
                    "net_profit": 9.0,
                    "maximum_drawdown": 2.0,
                    "by_strategy": {"range_reversion": 3},
                },
            },
        ],
    }

    summary = performance_from_campaign_payload(payload)

    assert summary.total_trades == 5
    assert summary.net_profit == 17.0
    assert summary.expectancy == 3.4
    assert summary.profit_factor == 22.0 / 5.0
    assert summary.by_symbol == {"BTC/USDT": 2, "ETH/USDT": 3}
    assert summary.by_strategy == {"trend_pullback": 2, "range_reversion": 3}


def test_load_performance_report_accepts_campaign_payload(tmp_path: Path) -> None:
    report = tmp_path / "campaign.json"
    report.write_text(
        json.dumps(
            {
                "best_variant_id": "candidate",
                "variants": [
                    {
                        "symbol": "BTC/USDT",
                        "variant": {"identifier": "candidate"},
                        "metrics": {
                            "total_trades": 2,
                            "win_rate": 0.5,
                            "gross_profit": 6.0,
                            "gross_loss": -2.0,
                            "net_profit": 4.0,
                            "maximum_drawdown": 1.0,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = load_performance_report(report)

    assert summary.total_trades == 2
    assert summary.net_profit == 4.0


def test_walk_forward_split_requires_chronological_boundaries() -> None:
    try:
        WalkForwardSplit(
            train_start="2026-02-01",
            train_end="2026-01-01",
            validation_start="2026-03-01",
            validation_end="2026-04-01",
            out_of_sample_start="2026-05-01",
            out_of_sample_end="2026-06-01",
        )
    except ValueError as exc:
        assert "chronological" in str(exc)
    else:
        raise AssertionError("expected invalid split to be rejected")


def test_walk_forward_calibration_keeps_final_test_isolated() -> None:
    split = WalkForwardSplit(
        train_start="2026-01-01",
        train_end="2026-02-01",
        validation_start="2026-02-02",
        validation_end="2026-03-01",
        out_of_sample_start="2026-03-02",
        out_of_sample_end="2026-04-01",
    )
    run_config = OptimizationRunConfig(
        identifier="walk-forward",
        variable_group=OptimizationGroup.SCORING_THRESHOLDS,
        minimum_trades=1,
        maximum_symbol_trade_share=1.0,
        split=split,
    )
    parameter_set = CandidateParameterSet(
        identifier="candidate",
        group=OptimizationGroup.SCORING_THRESHOLDS,
        parameters={"minimum_score": 65.0},
    )

    evaluation = evaluate_walk_forward_calibration(
        split=split,
        run_config=run_config,
        parameter_set=parameter_set,
        train_baseline=_summary(expectancy=10.0),
        train_candidate=_summary(expectancy=11.0, profit_factor=1.5),
        validation_baseline=_summary(expectancy=10.0),
        validation_candidate=_summary(expectancy=11.0, profit_factor=1.5),
        final_test_baseline=_summary(expectancy=5.0),
        final_test_candidate=_summary(expectancy=100.0, profit_factor=5.0),
    )
    payload = calibration_to_payload(evaluation)

    assert evaluation.decision is OptimizationDecision.ACCEPTED
    assert payload["final_test"]["used_for_selection"] is False
    assert payload["recommended_patch"] == {"scoring_thresholds": {"minimum_score": 65.0}}


def test_calibration_rejects_final_test_selection() -> None:
    split = WalkForwardSplit(
        train_start="2026-01-01",
        train_end="2026-02-01",
        validation_start="2026-02-02",
        validation_end="2026-03-01",
        out_of_sample_start="2026-03-02",
        out_of_sample_end="2026-04-01",
    )
    run_config = OptimizationRunConfig(
        identifier="walk-forward",
        variable_group=OptimizationGroup.SCORING_THRESHOLDS,
        split=split,
    )
    parameter_set = CandidateParameterSet(
        identifier="candidate",
        group=OptimizationGroup.SCORING_THRESHOLDS,
        parameters={"minimum_score": 65.0},
    )
    result = compare_performance(
        _summary(),
        _summary(expectancy=11.0, profit_factor=1.5),
        run_config=run_config,
        parameter_set=parameter_set,
    )

    try:
        CalibrationEvaluation(
            split=split,
            run_config=run_config,
            parameter_set=parameter_set,
            train_result=result,
            validation_result=result,
            final_test_used_for_selection=True,
            reasons=("should fail",),
        )
    except ValueError as exc:
        assert "final test" in str(exc)
    else:
        raise AssertionError("expected final-test selection to be rejected")
