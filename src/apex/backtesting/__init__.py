"""Focused public API for deterministic chronological backtesting."""

from apex.backtesting.acceptance_reporting import build_acceptance_reporting_payload
from apex.backtesting.calibration_reporting import (
    calibration_acceptance_from_report,
    calibration_metrics_from_report,
    calibration_reporting_payload,
)
from apex.backtesting.contracts import (
    BacktestConfig,
    BacktestOutcome,
    BacktestReport,
    BacktestRequest,
    BacktestSignal,
    BacktestStudy,
    SimulatedTrade,
)
from apex.backtesting.discovery_signal import signal_from_discovery_setup
from apex.backtesting.drawdown_reporting import (
    DrawdownAcceptanceReport,
    drawdown_acceptance_payload,
    evaluate_drawdown_acceptance,
)
from apex.backtesting.engine import HistoricalBacktestRunner, simulate_trade, summarize_trades
from apex.backtesting.evidence_coverage import (
    CalibrationEvidenceCoverage,
    build_calibration_evidence_coverage,
    calibration_evidence_coverage_payload,
)
from apex.backtesting.historical_signal_replay import (
    HistoricalCandleSeries,
    HistoricalCandleStore,
    HistoricalReplayBoundaries,
    HistoricalReplayPoint,
    HistoricalReplayProvider,
    HistoricalSignalSplit,
    build_replay_points,
)
from apex.backtesting.partition_reporting import (
    PartitionPerformance,
    PartitionStabilityReport,
    build_partition_stability_report,
    partition_stability_payload,
)
from apex.backtesting.regime_reporting import (
    RegimePerformance,
    RegimeStabilityReport,
    build_regime_stability_report,
    regime_stability_payload,
)

__all__ = [
    "BacktestConfig",
    "BacktestOutcome",
    "BacktestReport",
    "BacktestRequest",
    "BacktestSignal",
    "BacktestStudy",
    "CalibrationEvidenceCoverage",
    "DrawdownAcceptanceReport",
    "HistoricalBacktestRunner",
    "HistoricalCandleSeries",
    "HistoricalCandleStore",
    "HistoricalReplayBoundaries",
    "HistoricalReplayPoint",
    "HistoricalReplayProvider",
    "HistoricalSignalSplit",
    "PartitionPerformance",
    "PartitionStabilityReport",
    "RegimePerformance",
    "RegimeStabilityReport",
    "SimulatedTrade",
    "build_acceptance_reporting_payload",
    "build_calibration_evidence_coverage",
    "build_partition_stability_report",
    "build_regime_stability_report",
    "build_replay_points",
    "calibration_acceptance_from_report",
    "calibration_evidence_coverage_payload",
    "calibration_metrics_from_report",
    "calibration_reporting_payload",
    "drawdown_acceptance_payload",
    "evaluate_drawdown_acceptance",
    "partition_stability_payload",
    "regime_stability_payload",
    "signal_from_discovery_setup",
    "simulate_trade",
    "summarize_trades",
]
