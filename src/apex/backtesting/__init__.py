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
from apex.backtesting.historical_edge import (
    DEFAULT