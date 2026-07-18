"""Aggregate canonical methodology state for one analyzed candidate or symbol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.market_usability import (
    MarketUsabilityAssessment,
    market_usability_payload,
)
from apex.application.methodology_calibration_contracts import CalibrationProvenance
from apex.application.methodology_contracts import (
    ConfidenceAssessment,
    Contradiction,
    DurationExpectation,
    Entry