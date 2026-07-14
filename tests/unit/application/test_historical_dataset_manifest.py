from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apex.application.historical_dataset_manifest import (
    DatasetIssueCode,
    DatasetValidationState,
    build_curated_dataset_manifest,
    canonical_candle_content_hash,
    validate_curated_candles,
)
from apex.application.historical_edge import DatasetPartition, DatasetSplit, MarketType

_START = datetime(2026, 1