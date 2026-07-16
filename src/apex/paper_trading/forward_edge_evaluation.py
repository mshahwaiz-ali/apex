"""Deterministic forward-paper evidence aggregation and promotion."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from statistics import fmean

from apex.backtesting.historical_edge import EvidenceQuality
from apex.backtesting.historical_edge_validation import (
    HistoricalEdgeValidationResult,
    HistoricalEdgeValidationStatus,