"""Deterministic historical signal campaign contracts and persistence."""

from apex.historical_signals.backtest_binding import (
    HistoricalBacktestSignalInputs,
    load_historical_backtest_signal_inputs,
    verify_historical_backtest_signal_inputs,
)
from apex.historical_signals.contracts import (
    HISTORICAL_SIGNAL_CAMPAIGN_SCHEMA_VERSION,
    HISTORICAL_SIGNAL_RECORD_SCHEMA_VERSION,
    HistoricalSignalCampaignManifest,
    HistoricalSignalCampaignRecord,
    HistoricalSignalSourceDataset,
    derive_historical_signal_campaign_id,
    derive_historical_signal_record_id,
    validate_historical_signal_record_sequence,
)
from apex.historical_signals.generation import (
    derive_historical_signal_assumptions_hash,
    generate_and_persist_historical_signal_campaign,
)
from apex.historical_signals.persistence import (
    HistoricalSignalPersistenceError,
    hash_file_sha256,
    load_historical_signal_campaign_manifest,
    load_historical_signal_records,
    persist_completed_historical_signal_campaign,
    write_historical_signal_campaign_manifest,
    write_historical_signal_records,
)

__all__ = [
    "HISTORICAL_SIGNAL_CAMPAIGN_SCHEMA_VERSION",
    "HISTORICAL_SIGNAL_RECORD_SCHEMA_VERSION",
    "HistoricalBacktestSignalInputs",
    "HistoricalSignalCampaignManifest",
    "HistoricalSignalCampaignRecord",
    "HistoricalSignalPersistenceError",
    "HistoricalSignalSourceDataset",
    "derive_historical_signal_assumptions_hash",
    "derive_historical_signal_campaign_id",
    "derive_historical_signal_record_id",
    "generate_and_persist_historical_signal_campaign",
    "hash_file_sha256",
    "load_historical_backtest_signal_inputs",
    "load_historical_signal_campaign_manifest",
    "load_historical_signal_records",
    "persist_completed_historical_signal_campaign",
    "validate_historical_signal_record_sequence",
    "verify_historical_backtest_signal_inputs",
    "write_historical_signal_campaign_manifest",
    "write_historical_signal_records",
]
