"""Chronological dataset splits and leakage guards for historical edge studies."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.backtesting.contracts import SimulatedTrade


class HistoricalEdgeSplitRole(StrEnum):
    """Purpose assigned to one chronological evidence partition."""

    TRAIN = "train"
    VALIDATION