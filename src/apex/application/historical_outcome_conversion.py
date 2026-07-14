"""Deterministic conversion of completed backtest trades into historical outcomes."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.application.historical_edge import (
    DatasetPartition,
    DatasetSplit,
    HistoricalOutcome,
    MarketType,
)
from apex.backtesting import BacktestOutcome, SimulatedTrade


class OutcomeRejectionReason(StrEnum):
    """Aud