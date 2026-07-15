"""Immutable contracts for reproducible historical futures signal campaigns."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from apex.backtesting.historical_signal_replay import HistoricalSignalSplit

HISTORICAL_SIGNAL_RECORD_SCHEMA_VERSION: Final = 