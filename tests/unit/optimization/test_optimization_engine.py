import json

from apex.optimization import (
    CandidateParameterSet,
    OptimizationDecision,
    OptimizationGroup,
    OptimizationRunConfig,
    PerformanceSummary,
    compare_performance,
    load_performance_report,
    save_optimization_result,
)


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


def test_candidate_is_accepted_when_metrics_preserve_baseline() -> None:
    result = compare_performance(
        _summary(),
        _summary(expectancy=12.0, profit_factor=1.5, drawdown=95.0),
        run_config=OptimizationRunConfig(
            identifier="test",
            variable_group=OptimizationGroup.SCORING_THRESHOLDS,
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


def test_report_round_trip_does_not_mutate_config(tmp_path) -> None:
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
