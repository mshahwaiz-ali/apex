"""Typed contracts for setup-specific forward-paper evidence."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from apex.backtesting.historical_edge import EvidenceQuality
from apex.backtesting.historical_edge_validation import HistoricalEdgeValidationResult


class ForwardPaperValidationStatus(StrEnum):
    INSUFFICIENT_SAMPLE