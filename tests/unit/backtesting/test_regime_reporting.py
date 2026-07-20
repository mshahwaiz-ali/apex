from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.backtesting import (
    BacktestOutcome,
    BacktestSignal,
    RegimePerformance,
    SimulatedTrade,
    build_regime_stability_report,
    regime_stability_payload,
    summarize_trades,
)
from apex.strategies import StrategyType, TradeDirection


def _report(*net_pnls: float):
    return summarize_trades(
        tuple(_trade(index=index, net_pnl=value) for index, value in enumerate(net_pnls))
    )


def _trade(*, index: int, net_pnl: float) -> SimulatedTrade:
    signal = BacktestSignal(
        symbol=f"REGIME{index}USDT",
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        direction=TradeDirection.LONG,
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        entry_price=100.0,
        stop_price=95.0,
        target_price=110.0,
        quantity=1.0,
        risk_amount=5.0,
        confidence_score=70.0,
    )
    outcome = BacktestOutcome.TARGET if net_pnl > 0.0 else BacktestOutcome.STOP
    return SimulatedTrade(
        signal=signal,
        outcome=outcome,
        exit_time=datetime(2026, 1, 2, tzinfo=UTC),
        exit_price=110.0 if net_pnl > 0.0 else 95.0,
        gross_pnl=net_pnl,
        fees=0.0,
        net_pnl=net_pnl,
        realized_r_multiple=net_pnl / 5.0,
        holding_candles=2,
    )


def test_regime_reporting_is_deterministic_and_non_authoritative() -> None:
    report = build_regime_stability_report(
        {
            "volatile": _report(2.0, 4.0),
            "trend": _report(4.0, 6.0),
        }
    )

    assert tuple(item.regime for item in report.regimes) == ("trend", "volatile")
    assert report.regime_count == 2
    assert report.sampled_regime_count == 2
    assert report.all_regimes_sampled is True
    assert report.all_expectancies_positive is True
    assert report.expectancy_spread == pytest.approx(2.0)
    assert report.stable_regime_performance is True
    assert report.blockers == ()
    assert report.calibration_authoritative is False


def test_regime_reporting_fails_closed_with_insufficient_coverage() -> None:
    report = build_regime_stability_report({"trend": _report(4.0)})
    payload = regime_stability_payload(report)

    assert report.stable_regime_performance is None
    assert report.all_expectancies_positive is None
    assert report.expectancy_spread is None
    assert report.blockers == ("insufficient_regime_coverage",)
    assert payload["calibration_authoritative"] is False


def test_empty_regime_blocks_stability_conclusions() -> None:
    report = build_regime_stability_report(
        {
            "range": _report(),
            "trend": _report(4.0),
        }
    )

    assert report.all_regimes_sampled is False
    assert report.stable_regime_performance is None
    assert report.blockers == ("regime_samples_incomplete",)


def test_negative_regime_expectancy_is_reported_as_unstable() -> None:
    report = build_regime_stability_report(
        {
            "range": _report(-2.0),
            "trend": _report(4.0),
        }
    )

    assert report.all_expectancies_positive is False
    assert report.stable_regime_performance is False
    assert report.blockers == ()
    assert report.calibration_authoritative is False


def test_regime_performance_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="regime name"):
        RegimePerformance(
            regime=" ",
            sample_size=1,
            expectancy=1.0,
            profit_factor=2.0,
            average_r=1.0,
            maximum_drawdown=0.0,
            positive_expectancy=True,
        )
