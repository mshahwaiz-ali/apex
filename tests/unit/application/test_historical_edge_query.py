from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.application.historical_edge import (
    DatasetPartition,
    DatasetSplit,
    EvidenceQuality,
    EvidenceThresholds,
    HistoricalOutcome,
    MarketType,
    build_dataset_metadata,
)
from apex.application.historical_edge_io import (
    load_historical_edge_report_sqlite,
    write_historical_dataset_sqlite,
    write_historical_outcomes_sqlite,
)
from