"""Deterministic planning for historical futures dataset campaigns."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from apex.backtesting.dataset_acquisition import MAXIMUM_DATASET_CANDLES
from apex.backtesting.dataset_split import FuturesDatasetSplitRatios

FUTURES_DATASET_CAMPAIGN_SCHEMA_VERSION: Final = 2
LEGACY_FUTURES_DATASET_CAMPAIGN_SCHEMA_VERSION: Final = 1
CANONICAL_CAMPAIGN_TIMEFRAMES: Final[tuple[str, ...]] = (
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "4h",
)
_TIMEFRAME_ORDER: Final = {
    timeframe: index for index, timeframe in enumerate(CANONICAL_CAMPAIGN_TIMEFRAMES)
}
_TIMEFRAME_PATTERN: Final = re.compile(r"^[1-9][0-9]*[mhdwM]$")


class CampaignExecutionJobLike(Protocol):
    acquisition_order: int
    symbol: str
    timeframe: str


class CampaignExecutionResultLike(Protocol):
    jobs: tuple[CampaignExecutionJobLike, ...]


@dataclass(frozen=True, slots=True)
class FuturesDatasetCampaignJob:
    """One planned parent acquisition and its deterministic split artifacts."""

    acquisition_order: int
    symbol: str