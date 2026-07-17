"""Focused public API for deterministic chronological backtesting."""

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
from apex.backtesting.engine import HistoricalBacktestRunner, simulate_trade, summarize_trades
from apex.backtesting.historical_signal_replay import (
    HistoricalCandleSeries,
    HistoricalCandleStore,
    HistoricalReplayBoundaries,
    HistoricalReplayPoint,
    HistoricalReplayProvider,
    HistoricalSignalSplit,
    build_replay_points,
)

__all__ = [
    "BacktestConfig",
    "BacktestOutcome",
    "BacktestReport",
    "BacktestRequest",
    "BacktestSignal",
    "BacktestStudy",
    "HistoricalBacktestRunner",
    "HistoricalCandleSeries",
    "HistoricalCandleStore",
    "HistoricalReplayBoundaries",
    "HistoricalReplayPoint",
    "HistoricalReplayProvider",
    "HistoricalSignalSplit",
    "SimulatedTrade",
    "build_replay_points",
    "signal_from_discovery_setup",
    "simulate_trade",
    "summarize_trades",
]
