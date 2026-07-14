"""Typed contracts for deterministic walk-forward calibration."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType


class CalibrationDecision(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class CalibrationReason(StrEnum):
    TRAIN_SAMPLE_INSUFFICIENT = "TRAIN_SAMPLE_INSUFFICIENT"
    VALIDATION_SAMPLE_INSUFFICIENT = "VALIDATION_SAMPLE_INSUFFICIENT"
    VALIDATION_EXPECTANCY_NOT_IMPROVED = "VALIDATION_EXPECTANCY_NOT_IMPROVED"
    VALIDATION_DRAWDOWN_WORSE = "VALIDATION_DRAWDOWN_WORSE"
    SYMBOL_STABILITY_INSUFFICIENT = "SYMBOL_STABILITY_INSUFFICIENT"
    REGIME_STABILITY_INSUFFICIENT = "REGIME_STABILITY_INSUFFICIENT"
    FINAL_TEST_NOT_EVALUATED = "FINAL_TEST_NOT_EVALUATED"
    FINAL_TEST_DEGRADED = "FINAL_TEST_DEGRADED"
    CHANGE_ACCEPTED = "CHANGE_ACCEPTED"


@dataclass(frozen=True, slots=True)
class CalibrationPolicy:
    minimum_train_trades: int = 100
    minimum_validation_trades: int = 50
    minimum_expectancy_improvement: float = 0.0
    maximum_drawdown_increase_r: float = 0.0
    minimum_stable_symbols: int = 2
    minimum_stable_regimes: int = 2
    maximum_final_test_expectancy_degradation: float = 0.40

    def __post_init__(self) -> None:
        for name in (
            "minimum_train_trades",
            "minimum_validation_trades",
            "minimum_stable_symbols",
            "minimum_stable_regimes",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name.replace('_', ' ')} must be positive")
        for name in (
            "minimum_expectancy_improvement",
            "maximum_drawdown_increase_r",
            "maximum_final_test_expectancy_degradation",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class CalibrationMetrics:
    sample_size: int
    expectancy: float
    maximum_drawdown_r: float
    expectancy_by_symbol: Mapping[str, float]
    expectancy_by_regime: Mapping[str, float]

    def __post_init__(self) -> None:
        if self.sample_size < 1:
            raise ValueError("calibration metrics require at least one trade")
        for name in ("expectancy", "maximum_drawdown_r"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name.replace('_', ' ')} must be finite")
        if self.maximum_drawdown_r < 0.0:
            raise ValueError("maximum drawdown cannot be negative")
        for mapping_name in ("expectancy_by_symbol", "expectancy_by_regime"):
            mapping = getattr(self, mapping_name)
            if any(not key.strip() or not math.isfinite(value) for key, value in mapping.items()):
                raise ValueError(
                    f"{mapping_name.replace('_', ' ')} must contain finite named values"
                )
            object.__setattr__(self, mapping_name, MappingProxyType(dict(mapping)))


@dataclass(frozen=True, slots=True)
class CalibrationCandidate:
    identifier: str
    strategy: str
    parameter_changes: Mapping[str, str | int | float | bool]
    baseline_train: CalibrationMetrics
    candidate_train: CalibrationMetrics
    baseline_validation: CalibrationMetrics
    candidate_validation: CalibrationMetrics

    def __post_init__(self) -> None:
        if not self.identifier.strip() or not self.strategy.strip():
            raise ValueError("calibration candidate identity and strategy are required")
        if not self.parameter_changes:
            raise ValueError("calibration candidate requires parameter changes")
        object.__setattr__(
            self, "parameter_changes", MappingProxyType(dict(self.parameter_changes))
        )


@dataclass(frozen=True, slots=True)
class CalibrationAssessment:
    candidate_id: str
    strategy: str
    decision: CalibrationDecision
    validation_expectancy_improvement: float
    validation_drawdown_change_r: float
    stable_symbols: tuple[str, ...]
    stable_regimes: tuple[str, ...]
    reasons: tuple[CalibrationReason, ...]

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or not self.strategy.strip():
            raise ValueError("calibration assessment identity is required")
        for name in ("validation_expectancy_improvement", "validation_drawdown_change_r"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name.replace('_', ' ')} must be finite")
        if not self.reasons:
            raise ValueError("calibration assessment requires reasons")


@dataclass(frozen=True, slots=True)
class FinalTestAssessment:
    candidate_id: str
    decision: CalibrationDecision
    baseline_metrics: CalibrationMetrics
    candidate_metrics: CalibrationMetrics
    expectancy_degradation_from_validation: float | None
    reasons: tuple[CalibrationReason, ...]

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or not self.reasons:
            raise ValueError("final-test assessment requires candidate identity and reasons")
        if self.expectancy_degradation_from_validation is not None and not math.isfinite(
            self.expectancy_degradation_from_validation
        ):
            raise ValueError("final-test degradation must be finite")


@dataclass(frozen=True, slots=True)
class WalkForwardCalibrationReport:
    report_id: str
    assessments: tuple[CalibrationAssessment, ...]
    selected_candidate_ids: tuple[str, ...]
    final_test_assessments: tuple[FinalTestAssessment, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.report_id.strip() or not self.assessments:
            raise ValueError("calibration report requires identity and assessments")
        known = {item.candidate_id for item in self.assessments}
        if not set(self.selected_candidate_ids).issubset(known):
            raise ValueError("selected calibration candidates must refer to assessments")
        if any(
            item.candidate_id not in self.selected_candidate_ids
            for item in self.final_test_assessments
        ):
            raise ValueError("final-test results may only be attached to preselected candidates")
