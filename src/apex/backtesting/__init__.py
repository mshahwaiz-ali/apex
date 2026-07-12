"""Public Phase 8 backtesting API."""

from apex.backtesting.contracts import (
    BacktestConfig,
    BacktestOutcome,
    BacktestReport,
    BacktestSignal,
    SimulatedTrade,
)
from apex.backtesting.engine import signal_from_setup, simulate_trade, summarize_trades

__all__ = [
    "BacktestConfig",
    "BacktestOutcome",
    "BacktestReport",
    "BacktestSignal",
    "SimulatedTrade",
    "signal_from_setup",
    "simulate_trade",
    "summarize_trades",
]
