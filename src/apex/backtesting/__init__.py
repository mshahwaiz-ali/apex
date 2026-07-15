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
from apex.backtesting.dataset import (
    FUTURES_DATASET_SCHEMA_VERSION,
    FuturesCandleDataset,
    FuturesDatasetManifest,
    build_futures_dataset,
    hash_candles,
    load_futures_dataset,
    validate_dataset_candles,
    write_futures_dataset,
)
from apex.backtesting.dataset_acquisition import (
    MAXIMUM_DATASET_CANDLES,
    acquire_futures_dataset,
    build_dataset_id,
)
from apex.backtesting.dataset_campaign import (
    CANONICAL_CAMPAIGN