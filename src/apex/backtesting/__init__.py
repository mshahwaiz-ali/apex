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
    DEFAULT_EDGE_SEGMENTS,
    EvidenceQuality,
    HistoricalEdgeProfile,
    aggregate_historical_edges,
    build_historical_edge_profile,
)

__all__ = [
    "DEFAULT_EDGE_SEGMENTS",
    "BacktestConfig",
    "BacktestOutcome",
    "BacktestReport",
    "BacktestRequest",
    "BacktestSignal",
    "BacktestStudy",
    "EvidenceQuality",
    "HistoricalBacktestRunner",
    "HistoricalEdgeProfile",
    "SimulatedTrade",
    "aggregate_historical_edges",
    "build_historical_edge_profile",
    "signal_from_setup",
    "simulate_trade",
    "summarize_trades",
]
