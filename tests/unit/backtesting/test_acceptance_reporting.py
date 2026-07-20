from __future__ import annotations

from datetime import UTC, datetime

from apex.backtesting import (
    BacktestOutcome,
    BacktestSignal,
    HistoricalSignalSplit,
    SimulatedTrade,
    build_acceptance_reporting_payload,
    build_partition_stability_report,
    build_regime_stability_report,
    summarize_trades,
)
from apex.strategies import StrategyType, TradeDirection


def _report(*net_pnls: float):
    return summarize_trades(
        tuple(_trade(index=index, net_pnl=value) for index, value in enumerate(net_pnls))
    )


def _trade(*, index: int, net_pnl: float) -> SimulatedTrade:
    signal = BacktestSignal(
        symbol=f"ACCEPT{index}USDT",
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
        metadata={
            "partial_target_count": 1 if net_pnl > 0.0 else 0,
            "maximum_favorable_excursion_r": 1.0 if net_pnl > 0.0 else 0.2,
            "maximum_adverse_excursion_r": 0.2 if net_pnl > 0.0 else 1.0,
        },
    )


def test_composite_output_keeps_partition_and_regime_evidence_separate() -> None:
    report = _report(4.0, -1.0)
    partitions = build_partition_stability_report(
        {
            HistoricalSignalSplit.TRAIN: _report(4.0),
            HistoricalSignalSplit.VALIDATION: _report(3.0),
            HistoricalSignalSplit.FINAL_TEST: _report(2.0),
        }
    )
    regimes = build_regime_stability_report(
        {
            "range": _report(2.0),
            "trend": _report(4.0),
        }
    )

    payload = build_acceptance_reporting_payload(
        report,
        partitions=partitions,
        regimes=regimes,
    )

    assert payload["partitions"] is not None
    assert payload["regimes"] is not None
    acceptance = payload["acceptance"]
    assert isinstance(acceptance, dict)
    assert acceptance["stable_regime_performance"] is True
    assert acceptance["acceptable_drawdown"] is None
    assert payload["calibration_authoritative"] is False


def test_partition_stability_does_not_substitute_for_regime_stability() -> None:
    report = _report(4.0)
    partitions = build_partition_stability_report(
        {
            HistoricalSignalSplit.TRAIN: _report(4.0),
            HistoricalSignalSplit.VALIDATION: _report(3.0),
            HistoricalSignalSplit.FINAL_TEST: _report(2.0),
        }
    )

    payload = build_acceptance_reporting_payload(
        report,
        partitions=partitions,
        maximum_drawdown_limit=100.0,
    )

    acceptance = payload["acceptance"]
    assert isinstance(acceptance, dict)
    assert acceptance["stable_regime_performance"] is None
    assert "regime_stability_unavailable" in acceptance["blockers"]
    assert payload["calibration_authoritative"] is False


def test_unstable_regime_evidence_blocks_acceptance() -> None:
    report = _report(4.0)
    regimes = build_regime_stability_report(
        {
            "range": _report(-2.0),
            "trend": _report(4.0),
        }
    )

    payload = build_acceptance_reporting_payload(
        report,
        regimes=regimes,
        maximum_drawdown_limit=100.0,
    )

    acceptance = payload["acceptance"]
    assert isinstance(acceptance, dict)
    assert acceptance["stable_regime_performance"] is False
    assert "regime_performance_unstable" in acceptance["blockers"]
    assert payload["calibration_authoritative"] is False


def test_complete_external_gates_still_cannot_override_missing_metrics() -> None:
    report = _report(4.0)
    regimes = build_regime_stability_report(
        {
            "range": _report(2.0),
            "trend": _report(4.0),
        }
    )

    payload = build_acceptance_reporting_payload(
        report,
        regimes=regimes,
        maximum_drawdown_limit=100.0,
    )

    acceptance = payload["acceptance"]
    assert isinstance(acceptance, dict)
    assert acceptance["positive_expectancy"] is True
    assert acceptance["stable_regime_performance"] is True
    assert acceptance["acceptable_drawdown"] is True
    assert "required_metrics_incomplete" in acceptance["blockers"]
    assert payload["calibration_authoritative"] is False


def test_composite_output_exposes_evidence_coverage() -> None:
    payload = build_acceptance_reporting_payload(_report(4.0))

    coverage = payload["evidence_coverage"]
    assert isinstance(coverage, dict)
    assert coverage["complete"] is False
    assert coverage["calibration_authoritative"] is False
    assert "runner_success_rate" in coverage["missing_metrics"]
