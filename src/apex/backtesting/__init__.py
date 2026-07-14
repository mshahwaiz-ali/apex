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
from apex.backtesting.historical_edge_io import (
    HISTORICAL_EDGE_DB_SCHEMA_VERSION,
    HISTORICAL_EDGE_REPORT_SCHEMA_VERSION,
    build_historical_edge_report,
    list_historical_edge_report_metadata_sqlite,
    load_historical_edge_report,
    load_historical_edge_report_sqlite,
    write_historical_edge_report,
    write_historical_edge_report_sqlite,
)

__all__ = [
    "DEFAULT_EDGE_SEGMENTS",
    "HISTORICAL_EDGE_DB_SCHEMA_VERSION",
    "HISTORICAL_EDGE_REPORT_SCHEMA_VERSION",
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
    "build_historical_edge_report",
    "list_historical_edge_report_metadata_sqlite",
    "load_historical_edge_report",
    "load_historical_edge_report_sqlite",
    "signal_from_setup",
    "simulate_trade",
    "summarize_trades",
    "write_historical_edge_report",
    "write_historical_edge_report_sqlite",
]
