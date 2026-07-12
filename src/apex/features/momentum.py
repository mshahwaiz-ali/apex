"""Deterministic momentum features for normalized candle sequences."""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass

from apex.domain.models import Candle
from apex.features.contracts import (
    FeatureOutputShape,
    FeatureResult,
    FeatureSpec,
    MissingDataPolicy,
)
from apex.features