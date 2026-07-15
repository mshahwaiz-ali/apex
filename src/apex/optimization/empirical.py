"""Deterministic S10 empirical calibration reporting."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apex.optimization.contracts import (
    CandidateParameterSet,
    OptimizationDecision,
    OptimizationRunConfig,
    PerformanceSummary,
    WalkForwardSplit,
)
from apex.optimization.engine import (
    calibration_to_payload,
    evaluate_walk_forward_calibration,
   