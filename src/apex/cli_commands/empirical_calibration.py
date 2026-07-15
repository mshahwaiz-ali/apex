"""CLI workflow for deterministic S10 empirical calibration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, cast

import typer

from apex.optimization import (
    CandidateParameterSet,
    OptimizationGroup,
    OptimizationRunConfig,
    StabilityPolicy,
    WalkForwardSplit,
    build_empirical_calibration_report,
    load_and_verify_empirical_calibration_report,
    performance_from_mapping,
    write_empirical