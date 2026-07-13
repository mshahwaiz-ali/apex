"""Typed composition boundary for deterministic feature calculations."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from apex.domain.models import Candle
from apex.features.contracts import (
    FeatureOutputShape,
    FeatureResult,
    FeatureSpec,
    MissingDataPolicy,
)
from apex.features.momentum import macd, rate_of_change, relative_strength_index, rsi_slope
from apex.features.moving_