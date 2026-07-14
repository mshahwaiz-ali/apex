"""Typed contracts for V2 baseline campaign evaluation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from apex.backtesting import HistoricalEdgeProfile


class BaselineVerdict(StrEnum):
    ACCEPT = "ACCEPT"
    RESTRICT = "RESTRICT"
    REJECT = "REJECT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class BaselineReason(StrEnum):
    SAMPLE_INSUFFICIENT = "SAMPLE_INSUFFICIENT"
    EXPECTANCY_NOT_POSITIVE = "EXPECTANCY_NOT_POSITIVE"
    PROFIT_FACTOR_INADEQUATE = "PROFIT_FACTOR_INADEQUATE"
    DRAWDOWN_EXCESSIVE = "DRAWDOWN_EXCESSIVE"
    SYMBOL_COVERAGE_INSUFFICIENT = "SYMBOL_COVERAGE_INSUFFICIENT"
    REGIME_COVERAGE_INSUFFICIENT = "REGIME_COVERAGE_INSUFFICIENT"
    COST_SENSITIVITY_EXCESSIVE = "COST_SENSITIVITY_EXCESSIVE"
    BASELINE_ACCEPTED = "BASELINE_ACCEPTED"


@dataclass(frozen=True, slots=True)
class BaselineEvaluationPolicy:
    minimum_strategy_trades: int = 100
    minimum_symbols: int = 2
    minimum_regimes: int = 2
    minimum_profit_factor: float = 1.0
    maximum_drawdown_r: float = 20.0
    maximum_cost_expectancy_degradation: float = 0.60

    def __post_init__(self) -> None:
        for name in ("minimum_strategy_trades", "minimum_symbols", "minimum_regimes"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name.replace('_', ' ')} must be positive")
        for name in (
            "minimum_profit_factor",
            "maximum_drawdown_r",
            "maximum_cost_expectancy_degradation",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class BaselineScenario:
    identifier: str
    fee_pct: float
    slippage_pct: float
    profiles: tuple[HistoricalEdgeProfile, ...]

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ValueError("baseline scenario identifier cannot be empty")
        if not self.profiles:
            raise ValueError("baseline scenario requires historical edge profiles")
        for name in ("fee_pct", "slippage_pct"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class CostSensitivityResult:
    scenario_id: str
    expectancy: float
    degradation_from_baseline: float | None
    stable: bool

    def __post_init__(self) -> None:
        if not self.scenario_id.strip() or not math.isfinite(self.expectancy):
            raise ValueError("cost sensitivity scenario and expectancy are required")
        if self.degradation_from_baseline is not None and not math.isfinite(
            self.degradation_from_baseline
        ):
            raise ValueError("cost sensitivity degradation must be finite")


@dataclass(frozen=True, slots=True)
class StrategyBaselineAssessment:
    strategy: str
    verdict: BaselineVerdict
    sample_size: int
    expectancy: float
    profit_factor: float | None
    maximum_drawdown_r: float
    symbols: tuple[str, ...]
    regimes: tuple[str, ...]
    score_bands: Mapping[str, float]
    cost_sensitivity: tuple[CostSensitivityResult, ...]
    reasons: tuple[BaselineReason, ...]

    def __post_init__(self) -> None:
        if not self.strategy.strip() or self.sample_size < 1:
            raise ValueError("strategy assessment requires identity and trades")
        for name in ("expectancy", "maximum_drawdown_r"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name.replace('_', ' ')} must be finite")
        if self.profit_factor is not None and (
            not math.isfinite(self.profit_factor) or self.profit_factor < 0.0
        ):
            raise ValueError("profit factor must be finite and non-negative")
        if not self.reasons:
            raise ValueError("strategy assessment requires at least one reason")
        object.__setattr__(self, "score_bands", MappingProxyType(dict(self.score_bands)))


@dataclass(frozen=True, slots=True)
class BaselineEvaluationReport:
    plan_id: str
    baseline_scenario_id: str
    scenario_ids: tuple[str, ...]
    assessments: tuple[StrategyBaselineAssessment, ...]
    report_id: str
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.plan_id.strip() or not self.report_id.strip():
            raise ValueError("baseline report requires plan and report ids")
        if self.baseline_scenario_id not in self.scenario_ids:
            raise ValueError("baseline scenario must be included in scenario ids")
        if not self.assessments:
            raise ValueError("baseline report requires strategy assessments")
