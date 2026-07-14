"""Typed contracts for frozen V2 spot baseline campaigns."""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from apex.spot_backtesting import SpotBacktestResult


class SpotDatasetRole(StrEnum):
    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    TEST = "TEST"


class SpotBaselineVerdict(StrEnum):
    ACCEPT = "ACCEPT"
    RESTRICT = "RESTRICT"
    REJECT = "REJECT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class SpotBaselineReason(StrEnum):
    SAMPLE_INSUFFICIENT = "SAMPLE_INSUFFICIENT"
    EXPECTANCY_NOT_POSITIVE = "EXPECTANCY_NOT_POSITIVE"
    PROFIT_FACTOR_INADEQUATE = "PROFIT_FACTOR_INADEQUATE"
    DRAWDOWN_EXCESSIVE = "DRAWDOWN_EXCESSIVE"
    SYMBOL_COVERAGE_INSUFFICIENT = "SYMBOL_COVERAGE_INSUFFICIENT"
    REGIME_COVERAGE_INSUFFICIENT = "REGIME_COVERAGE_INSUFFICIENT"
    COST_SENSITIVITY_EXCESSIVE = "COST_SENSITIVITY_EXCESSIVE"
    EXPOSURE_EXCESSIVE = "EXPOSURE_EXCESSIVE"
    BASELINE_ACCEPTED = "BASELINE_ACCEPTED"


@dataclass(frozen=True, slots=True)
class SpotDatasetReference:
    dataset_id: str
    content_hash: str
    role: SpotDatasetRole
    symbols: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.dataset_id.strip() or not self.content_hash.strip():
            raise ValueError("spot dataset identity cannot be empty")
        if not self.symbols or any(not symbol.strip() for symbol in self.symbols):
            raise ValueError("spot dataset requires symbols")


@dataclass(frozen=True, slots=True)
class SpotCostVariant:
    identifier: str
    fee_pct: float
    slippage_pct: float

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ValueError("spot cost variant identifier cannot be empty")
        for name in ("fee_pct", "slippage_pct"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class SpotAllocationVariant:
    identifier: str
    maximum_allocation_per_position_pct: float
    maximum_total_exposure_pct: float
    maximum_concurrent_positions: int

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ValueError("spot allocation variant identifier cannot be empty")
        for name in (
            "maximum_allocation_per_position_pct",
            "maximum_total_exposure_pct",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0.0 < value <= 100.0:
                raise ValueError(f"{name.replace('_', ' ')} must be in (0, 100]")
        if self.maximum_allocation_per_position_pct > self.maximum_total_exposure_pct:
            raise ValueError("per-position allocation cannot exceed total exposure")
        if self.maximum_concurrent_positions < 1:
            raise ValueError("maximum concurrent positions must be positive")


@dataclass(frozen=True, slots=True)
class SpotCampaignCell:
    strategy: str
    symbol: str
    dataset_id: str
    dataset_role: SpotDatasetRole
    cost_variant_id: str
    allocation_variant_id: str

    @property
    def key(self) -> str:
        return "|".join(
            (
                self.strategy,
                self.symbol,
                self.dataset_id,
                self.dataset_role.value,
                self.cost_variant_id,
                self.allocation_variant_id,
            )
        )

    def __post_init__(self) -> None:
        if any(
            not value.strip()
            for value in (
                self.strategy,
                self.symbol,
                self.dataset_id,
                self.cost_variant_id,
                self.allocation_variant_id,
            )
        ):
            raise ValueError("spot campaign cell fields cannot be empty")


@dataclass(frozen=True, slots=True)
class SpotBaselineCampaignPlan:
    plan_id: str
    strategies: tuple[str, ...]
    symbols: tuple[str, ...]
    datasets: tuple[SpotDatasetReference, ...]
    cost_variants: tuple[SpotCostVariant, ...]
    allocation_variants: tuple[SpotAllocationVariant, ...]
    cells: tuple[SpotCampaignCell, ...]
    assumptions_hash: str

    def __post_init__(self) -> None:
        if not self.plan_id.strip() or not self.assumptions_hash.strip():
            raise ValueError("spot baseline plan identity cannot be empty")
        for name in (
            "strategies",
            "symbols",
            "datasets",
            "cost_variants",
            "allocation_variants",
            "cells",
        ):
            if not getattr(self, name):
                raise ValueError(f"spot baseline plan requires {name.replace('_', ' ')}")
        keys = [cell.key for cell in self.cells]
        if len(keys) != len(set(keys)):
            raise ValueError("spot baseline campaign cells must be unique")


@dataclass(frozen=True, slots=True)
class SpotCampaignResult:
    cell: SpotCampaignCell
    plan_id: str
    assumptions_hash: str
    dataset_content_hash: str
    backtest: SpotBacktestResult

    def __post_init__(self) -> None:
        if not self.plan_id.strip() or not self.assumptions_hash.strip():
            raise ValueError("spot campaign result identity cannot be empty")
        if not self.dataset_content_hash.strip():
            raise ValueError("spot campaign result requires dataset hash")


@dataclass(frozen=True, slots=True)
class SpotBaselineEvaluationPolicy:
    minimum_strategy_trades: int = 100
    minimum_symbols: int = 2
    minimum_regimes: int = 2
    minimum_profit_factor: float = 1.0
    maximum_drawdown_pct: float = 25.0
    maximum_cost_expectancy_degradation: float = 0.60
    maximum_average_exposure_pct: float = 80.0

    def __post_init__(self) -> None:
        if (
            self.minimum_strategy_trades < 1
            or self.minimum_symbols < 1
            or self.minimum_regimes < 1
        ):
            raise ValueError("spot baseline minimum counts must be positive")
        for name in (
            "minimum_profit_factor",
            "maximum_drawdown_pct",
            "maximum_cost_expectancy_degradation",
            "maximum_average_exposure_pct",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class SpotCostSensitivity:
    cost_variant_id: str
    expectancy_pct: float
    degradation_from_baseline: float | None
    stable: bool


@dataclass(frozen=True, slots=True)
class SpotStrategyAssessment:
    strategy: str
    verdict: SpotBaselineVerdict
    sample_size: int
    expectancy_pct: float
    profit_factor: float | None
    maximum_drawdown_pct: float
    total_return_pct: float
    symbols: tuple[str, ...]
    regimes: tuple[str, ...]
    score_bands: Mapping[str, float]
    average_exposure_pct: float
    maximum_exposure_pct: float
    average_concurrent_positions: float
    maximum_concurrent_positions: int
    cost_sensitivity: tuple[SpotCostSensitivity, ...]
    reasons: tuple[SpotBaselineReason, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "score_bands", MappingProxyType(dict(self.score_bands)))


@dataclass(frozen=True, slots=True)
class SpotBaselineReport:
    plan_id: str
    baseline_cost_variant_id: str
    baseline_allocation_variant_id: str
    assessments: tuple[SpotStrategyAssessment, ...]
    report_id: str
    warnings: tuple[str, ...] = field(
        default=(
            "historical spot results do not guarantee future returns",
            "strategy verdicts use train and validation cells only",
            "frozen final-test cells remain untouched by baseline selection",
            "forward-paper validation remains required",
        )
    )
