"""Immutable contracts for deterministic calibration and optimization."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class OptimizationGroup(StrEnum):
    SCORING_THRESHOLDS = "scoring_thresholds"
    RISK_THRESHOLDS = "risk_thresholds"
    STRATEGY_TOGGLES = "strategy_toggles"
    SYMBOL_FILTERS = "symbol_filters"


class OptimizationDecision(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class CalibrationStage(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    FINAL_TEST = "final_test"


@dataclass(frozen=True, slots=True)
class WalkForwardSplit:
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    out_of_sample_start: str
    out_of_sample_end: str

    def __post_init__(self) -> None:
        values = (
            self.train_start,
            self.train_end,
            self.validation_start,
            self.validation_end,
            self.out_of_sample_start,
            self.out_of_sample_end,
        )
        if any(not value.strip() for value in values):
            raise ValueError("walk-forward split boundaries cannot be empty")
        if values != tuple(sorted(values)):
            raise ValueError("walk-forward split boundaries must be chronological")


@dataclass(frozen=True, slots=True)
class CandidateParameterSet:
    identifier: str
    group: OptimizationGroup
    parameters: dict[str, str | int | float | bool]

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ValueError("candidate parameter identifier cannot be empty")
        if not self.parameters:
            raise ValueError("candidate parameters cannot be empty")
        for key, value in self.parameters.items():
            if not key.strip():
                raise ValueError("candidate parameter keys cannot be empty")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("candidate parameter values must be finite")
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


@dataclass(frozen=True, slots=True)
class OptimizationRunConfig:
    identifier: str
    variable_group: OptimizationGroup
    minimum_trades: int = 1
    minimum_expectancy_delta: float = 0.0
    maximum_drawdown_increase_pct: float = 0.0
    require_profit_factor_not_worse: bool = True
    reject_symbol_dependency: bool = True
    maximum_symbol_trade_share: float = 0.70
    reject_strategy_dependency: bool = False
    maximum_strategy_trade_share: float = 0.80
    split: WalkForwardSplit | None = None

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ValueError("optimization run identifier cannot be empty")
        if self.minimum_trades < 1:
            raise ValueError("minimum trades must be positive")
        for name in ("minimum_expectancy_delta", "maximum_drawdown_increase_pct"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be finite and non-negative")
        for name in ("maximum_symbol_trade_share", "maximum_strategy_trade_share"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0.0 < value <= 1.0:
                raise ValueError(f"{name.replace('_', ' ')} must be in the interval (0, 1]")


@dataclass(frozen=True, slots=True)
class PerformanceSummary:
    total_trades: int
    win_rate: float
    expectancy: float
    profit_factor: float | None
    maximum_drawdown: float
    net_profit: float
    by_symbol: dict[str, int]
    by_strategy: dict[str, int]
    by_regime: dict[str, int]
    by_score_band: dict[str, int]
    loss_rate: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0

    def __post_init__(self) -> None:
        if self.total_trades < 0:
            raise ValueError("total trades cannot be negative")
        for name in (
            "win_rate",
            "loss_rate",
            "expectancy",
            "maximum_drawdown",
            "net_profit",
            "average_win",
            "average_loss",
        ):
            value = getattr(self, name)
            if not math.isfinite(value):
                raise ValueError(f"{name.replace('_', ' ')} must be finite")
        for name in ("win_rate", "loss_rate"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name.replace('_', ' ')} must be in the unit interval")
        if self.maximum_drawdown < 0.0:
            raise ValueError("maximum drawdown cannot be negative")
        if self.profit_factor is not None and (
            not math.isfinite(self.profit_factor) or self.profit_factor < 0.0
        ):
            raise ValueError("profit factor must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    decision: OptimizationDecision
    run_config: OptimizationRunConfig
    baseline: PerformanceSummary
    candidate: PerformanceSummary
    parameter_set: CandidateParameterSet
    reasons: tuple[str, ...]
    recommended_patch: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.reasons:
            raise ValueError("optimization result requires reasons")
        if self.parameter_set.group is not self.run_config.variable_group:
            raise ValueError("parameter set group must match run variable group")
        object.__setattr__(
            self,
            "recommended_patch",
            MappingProxyType(dict(self.recommended_patch)),
        )


@dataclass(frozen=True, slots=True)
class CalibrationEvaluation:
    """Walk-forward calibration decision that keeps the final test isolated."""

    split: WalkForwardSplit
    run_config: OptimizationRunConfig
    parameter_set: CandidateParameterSet
    train_result: OptimizationResult
    validation_result: OptimizationResult
    final_test_baseline: PerformanceSummary | None = None
    final_test_candidate: PerformanceSummary | None = None
    final_test_used_for_selection: bool = False
    decision: OptimizationDecision = OptimizationDecision.REJECTED
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.run_config.split != self.split:
            raise ValueError("calibration split must match run configuration split")
        if self.parameter_set.group is not self.run_config.variable_group:
            raise ValueError("calibration parameter set must match run variable group")
        if self.final_test_used_for_selection:
            raise ValueError("final test set must remain isolated from calibration selection")
        if not self.reasons:
            raise ValueError("calibration evaluation requires reasons")
