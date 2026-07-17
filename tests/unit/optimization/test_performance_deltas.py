"""Tests for deterministic calibration performance deltas."""

from __future__ import annotations

from apex.optimization.contracts import (
    CandidateParameterSet,
    OptimizationGroup,
    OptimizationRunConfig,
    PerformanceSummary,
)
from apex.optimization.engine import compare_performance, result_to_payload


def _summary(
    *,
    total_trades: int,
    win_rate: float,
    loss_rate: float,
    expectancy: float,
    profit_factor: float | None,
    maximum_drawdown: float,
    net_profit: float,
    average_win: float,
    average_loss: float,
) -> PerformanceSummary:
    return PerformanceSummary(
        total_trades=total_trades,
        win_rate=win_rate,
        expectancy=expectancy,
        profit_factor=profit_factor,
        maximum_drawdown=maximum_drawdown,
        net_profit=net_profit,
        by_symbol={"BTCUSDT": total_trades},
        by_strategy={"trend_pullback": total_trades},
        by_regime={"trend": total_trades},
        by_score_band={"70-79": total_trades},
        loss_rate=loss_rate,
        average_win=average_win,
        average_loss=average_loss,
    )


def _payload(
    baseline: PerformanceSummary,
    candidate: PerformanceSummary,
) -> dict[str, object]:
    run_config = OptimizationRunConfig(
        identifier="performance-delta-test",
        variable_group=OptimizationGroup.SCORING_THRESHOLDS,
        minimum_trades=1,
        maximum_drawdown_increase_pct=100.0,
    )
    parameter_set = CandidateParameterSet(
        identifier="candidate",
        group=OptimizationGroup.SCORING_THRESHOLDS,
        parameters={"minimum_score": 70},
    )
    result = compare_performance(
        baseline,
        candidate,
        run_config=run_config,
        parameter_set=parameter_set,
    )
    return result_to_payload(result)


def test_result_payload_exposes_complete_performance_deltas() -> None:
    payload = _payload(
        _summary(
            total_trades=10,
            win_rate=0.40,
            loss_rate=0.50,
            expectancy=0.20,
            profit_factor=1.20,
            maximum_drawdown=5.0,
            net_profit=2.0,
            average_win=4.0,
            average_loss=-2.0,
        ),
        _summary(
            total_trades=12,
            win_rate=0.50,
            loss_rate=0.40,
            expectancy=0.35,
            profit_factor=1.50,
            maximum_drawdown=4.0,
            net_profit=4.2,
            average_win=4.5,
            average_loss=-1.5,
        ),
    )

    assert payload["performance_deltas"] == {
        "total_trades": 2,
        "win_rate": 0.10,
        "loss_rate": -0.10,
        "expectancy": 0.15,
        "profit_factor": 0.30,
        "maximum_drawdown": -1.0,
        "net_profit": 2.2,
        "average_win": 0.5,
        "average_loss": 0.5,
    }


def test_profit_factor_delta_is_none_when_either_value_is_unavailable() -> None:
    payload = _payload(
        _summary(
            total_trades=10,
            win_rate=0.40,
            loss_rate=0.50,
            expectancy=0.20,
            profit_factor=None,
            maximum_drawdown=5.0,
            net_profit=2.0,
            average_win=4.0,
            average_loss=-2.0,
        ),
        _summary(
            total_trades=10,
            win_rate=0.40,
            loss_rate=0.50,
            expectancy=0.20,
            profit_factor=1.50,
            maximum_drawdown=5.0,
            net_profit=2.0,
            average_win=4.0,
            average_loss=-2.0,
        ),
    )

    assert payload["performance_deltas"]["profit_factor"] is None


def test_performance_deltas_are_rounded_deterministically() -> None:
    payload = _payload(
        _summary(
            total_trades=3,
            win_rate=1 / 3,
            loss_rate=2 / 3,
            expectancy=0.1,
            profit_factor=1.1,
            maximum_drawdown=0.3,
            net_profit=0.3,
            average_win=0.2,
            average_loss=-0.1,
        ),
        _summary(
            total_trades=3,
            win_rate=2 / 3,
            loss_rate=1 / 3,
            expectancy=0.2,
            profit_factor=1.3,
            maximum_drawdown=0.2,
            net_profit=0.6,
            average_win=0.3,
            average_loss=-0.05,
        ),
    )

    deltas = payload["performance_deltas"]
    assert deltas["win_rate"] == 0.333333
    assert deltas["loss_rate"] == -0.333333
    assert deltas["expectancy"] == 0.1
    assert deltas["average_loss"] == 0.05
