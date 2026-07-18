"""Interpret methodology confidence without implying uncalibrated probability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_contracts import ConfidenceAssessment, ConfidenceBasis


@dataclass(frozen=True, slots=True)
class ConfidenceSemantics:
    """Public interpretation of confidence labels and calibration state."""

    available