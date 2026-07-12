"""Deterministic range and consolidation detection."""

from __future__ import annotations

import math
from collections.abc import Sequence

from apex.domain.models import Candle
from apex.features.validation import ActiveCandlePolicy, prepare_candles
from apex.structure.contracts import RangeBreakoutState, RangeStructure


def detect_range(
    candles: Sequence[Candle],
    *,
    lookback: int = 20,
    boundary_tolerance: float = 0.002,
    maximum_width_percentage: float = 0.08,
