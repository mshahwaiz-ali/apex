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
from apex.backtesting.historical_edge_split import (
    HistoricalEdgeSplit,
    HistoricalEdgeSplitConfig,
    HistoricalEdgeSplitRole,
    HistoricalEdgeSplitSet,
    split_historical_edge_trades,
)
from apex.backtesting.historical_edge_validation import (
    HistoricalEdgeValidationPolicy,
    HistoricalEdgeValidationReason,
    HistoricalEdgeValidationResult,
    HistoricalEdgeValidationStatus,
    evaluate_historical_edge_splits,
    validate_out_of_sample_edges,
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
    "HistoricalEdgeSplit",
    "HistoricalEdgeSplitConfig",
    "HistoricalEdgeSplitRole",
    "HistoricalEdgeSplitSet",
    "HistoricalEdgeValidationPolicy",
    "HistoricalEdgeValidationReason",
    "HistoricalEdgeValidationResult",
    "HistoricalEdgeValidationStatus",
    "SimulatedTrade",
    "aggregate_historical_edges",
    "build_historical_edge_profile",
    "build_historical_edge_report",
    "evaluate_historical_edge_splits",
    "list_historical_edge_report_metadata_sqlite",
    "load_historical_edge_report",
    "load_historical_edge_report_sqlite",
    "signal_from_setup",
    "simulate_trade",
    "split_historical_edge_trades",
    "summarize_trades",
    "validate_out_of_sample_edges",
    "write_historical_edge_report",
    "write_historical_edge_report_sqlite",
]
