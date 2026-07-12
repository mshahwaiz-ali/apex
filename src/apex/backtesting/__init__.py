"""Public Phase 8 backtesting API."""

from apex.backtesting.contracts import (
    BacktestConfig,
    BacktestOutcome,
    BacktestReport,
    BacktestRequest,
    BacktestSignal,
    BacktestStudy,
    SimulatedTrade,
)
from apex.backtesting.engine import (
    HistoricalBacktestRunner,
    signal_from_setup,
    simulate_trade,
    summarize_trades,
)

__all__ = [
    "BacktestConfig",
    "BacktestOutcome",
    "BacktestReport",
    "BacktestRequest",
    "BacktestSignal",
    "BacktestStudy",
    "HistoricalBacktestRunner",
    "SimulatedTrade",
    "signal_from_setup",
    "simulate_trade",
    "summarize_trades",
]
