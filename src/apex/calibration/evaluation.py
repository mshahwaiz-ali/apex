"""Deterministic walk-forward candidate selection and final-test attachment."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from apex.calibration.contracts import (
    CalibrationAssessment,
    CalibrationCandidate,
    CalibrationDecision,
    CalibrationMetrics,
    CalibrationPolicy,
    CalibrationReason,
    FinalTestAssessment,
    WalkForwardCalibrationReport,
)


def evaluate