"""Verified schema-v2 historical signal inputs for futures backtesting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from apex.backtesting.historical_signal_campaign import (
    HistoricalSignalCampaignInputs,
    load_historical_signal_campaign_inputs,
)
from apex.historical_signals.contracts import (
    HistoricalSignalCampaignManifest,
    HistoricalSignalCampaignRecord,
)
from apex.historical_signals.persistence import (
    hash_file_sha256,
    load_historical