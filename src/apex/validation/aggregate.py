"""Aggregate forward-paper validation history review."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.validation import ProductionEligibility
from apex.validation.history import DailyValidationRecord


class AggregateHistoryReason(StrEnum):
    """Stable machine-readable aggregate P1 blocker codes."""

    INSUFFICIENT_VALIDATION_DAYS = "INSUFFICIENT_VALIDATION_DAYS"
    INSUFFICIENT_TOTAL_SAMPLES = "INSUFFICIENT_TOTAL_SAMPLES"
    INSUFFICIENT_STRATEGY_SAMPLES = "INSUFFICIENT_STRATEGY_SAMPLES"
    INSU