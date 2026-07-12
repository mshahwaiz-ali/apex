"""Deterministic swing-high and swing-low detection."""

from __future__ import annotations

from collections.abc import Sequence

from apex.domain.models import Candle
from apex.features.validation import ActiveCandlePolicy, prepare_candles
from apex.structure.contracts import ComparisonPolicy, PivotStatus, SwingPoint, SwingType


def detect_swings(
    candles: Sequence[Candle],
    *,
    left_window: int = 2,
    right_window: int