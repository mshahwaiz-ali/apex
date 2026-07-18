"""Canonical volatility and normal-noise evidence for structural stop assessment."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class StopNoiseMeasure(StrEnum):
    """Supported reference measures for ordinary price noise."""

    ATR = "atr"
    REALIZED_RANGE = "realized_range"
    REALIZED_VOLATILITY = "realized_volatility"


@dataclass(frozen=True, slots=True)
class StopNoiseEvidence:
    """