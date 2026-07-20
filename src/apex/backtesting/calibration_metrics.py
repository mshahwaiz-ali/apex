"""Typed calibration metrics for Apex opportunity outcomes."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from statistics import fmean


class AlignmentClass(StrEnum):
    """Whether a trade followed or opposed the higher-timeframe structure."""

    ALIGNED = "aligned"
    COUNTERTREND = "countertrend"
    UNKNOWN = "unknown"


class OutcomeState(StrEnum):
    """Normalized terminal or censored outcome state."""

    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    MISSED = "missed"
    STALE = "stale"
    DEVELOPING = "developing"
    MARGIN_FAILURE = "margin_failure"


@dataclass(frozen=True, slots=True)
class CalibratedTradeOutcome:
    """One leakage-safe realized or censored opportunity outcome."""

    strategy: str
    regime: str
    confidence_band: str
    actionability_state: str
    alignment: AlignmentClass
    outcome_state: OutcomeState
    realized_r: float
    mfe_r: float
    mae_r: float
    tp1_hit: bool
    tp2_hit: bool
    runner_success: bool
    stop_hit: bool
    false_cmp_signal: bool
    fees_r: float = 0.0
    slippage_r: float = 0.0
    liquidation_or_margin_failure: bool = False

    def __post_init__(self) -> None:
        for name in ("strategy", "regime", "confidence_band", "actionability_state"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must not be empty")
        for name in ("realized_r", "mfe_r", "mae_r", "fees_r", "slippage_r"):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.mfe_r < 0:
            raise ValueError("mfe_r must be non-negative")
        if self.mae_r < 0:
            raise ValueError("mae_r must be non-negative")
        if self.fees_r < 0 or self.slippage_r < 0:
            raise ValueError("fees and slippage must be non-negative")

    @property
    def counted_trade(self) -> bool:
        """Return whether the sample belongs in realized expectancy statistics."""

        return self.outcome_state in {
            OutcomeState.WIN,
            OutcomeState.LOSS,
            OutcomeState.BREAKEVEN,
            OutcomeState.MARGIN_FAILURE,
        }

    @property
    def net_r(self) -> float:
        """Return realized R after explicit fees and slippage."""

        return self.realized_r - self.fees_r - self.slippage_r


@dataclass(frozen=True, slots=True)
class CalibrationMetrics:
    """Aggregate performance metrics with explicit sample counts."""

    total_observations: int
    counted_trades: int
    wins: int
    losses: int
    breakevens: int
    missed: int
    stale_or_developing: int
    win_rate: float | None
    profit_factor: float | None
    expectancy_r: float | None
    average_r: float | None
    tp1_hit_rate: float | None
    tp2_hit_rate: float | None
    runner_success_rate: float | None
    stop_rate: float | None
    false_cmp_signal_rate: float | None
    average_mfe_r: float | None
    average_mae_r: float | None
    total_fees_r: float
    total_slippage_r: float
    liquidation_or_margin_failure_rate: float | None


@dataclass(frozen=True, slots=True)
class CalibrationSlice:
    """One named calibration segment and its metrics."""

    dimension: str
    value: str
    metrics: CalibrationMetrics


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    """Overall metrics plus required methodology slices."""

    overall: CalibrationMetrics
    by_strategy: tuple[CalibrationSlice, ...]
    by_regime: tuple[CalibrationSlice, ...]
    by_confidence_band: tuple[CalibrationSlice, ...]
    by_actionability_state: tuple[CalibrationSlice, ...]
    by_alignment: tuple[CalibrationSlice, ...]


def calculate_calibration_metrics(
    outcomes: tuple[CalibratedTradeOutcome, ...],
) -> CalibrationMetrics:
    """Calculate required metrics without treating missed trades as wins."""

    counted = tuple(item for item in outcomes if item.counted_trade)
    wins = tuple(item for item in counted if item.net_r > 0)
    losses = tuple(item for item in counted if item.net_r < 0)
    breakevens = tuple(item for item in counted if item.net_r == 0)
    missed = sum(item.outcome_state is OutcomeState.MISSED for item in outcomes)
    stale_or_developing = sum(
        item.outcome_state in {OutcomeState.STALE, OutcomeState.DEVELOPING} for item in outcomes
    )

    gross_profit = sum(item.net_r for item in wins)
    gross_loss = abs(sum(item.net_r for item in losses))
    profit_factor = None
    if counted:
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else math.inf

    return CalibrationMetrics(
        total_observations=len(outcomes),
        counted_trades=len(counted),
        wins=len(wins),
        losses=len(losses),
        breakevens=len(breakevens),
        missed=missed,
        stale_or_developing=stale_or_developing,
        win_rate=_rate(len(wins), len(counted)),
        profit_factor=profit_factor,
        expectancy_r=_mean(tuple(item.net_r for item in counted)),
        average_r=_mean(tuple(item.net_r for item in counted)),
        tp1_hit_rate=_rate(sum(item.tp1_hit for item in counted), len(counted)),
        tp2_hit_rate=_rate(sum(item.tp2_hit for item in counted), len(counted)),
        runner_success_rate=_rate(
            sum(item.runner_success for item in counted),
            len(counted),
        ),
        stop_rate=_rate(sum(item.stop_hit for item in counted), len(counted)),
        false_cmp_signal_rate=_rate(
            sum(item.false_cmp_signal for item in outcomes),
            len(outcomes),
        ),
        average_mfe_r=_mean(tuple(item.mfe_r for item in counted)),
        average_mae_r=_mean(tuple(item.mae_r for item in counted)),
        total_fees_r=sum(item.fees_r for item in counted),
        total_slippage_r=sum(item.slippage_r for item in counted),
        liquidation_or_margin_failure_rate=_rate(
            sum(item.liquidation_or_margin_failure for item in counted),
            len(counted),
        ),
    )


def build_calibration_report(
    outcomes: tuple[CalibratedTradeOutcome, ...],
) -> CalibrationReport:
    """Build all required Batch 11 performance slices."""

    return CalibrationReport(
        overall=calculate_calibration_metrics(outcomes),
        by_strategy=_slice(outcomes, "strategy", lambda item: item.strategy),
        by_regime=_slice(outcomes, "regime", lambda item: item.regime),
        by_confidence_band=_slice(
            outcomes,
            "confidence_band",
            lambda item: item.confidence_band,
        ),
        by_actionability_state=_slice(
            outcomes,
            "actionability_state",
            lambda item: item.actionability_state,
        ),
        by_alignment=_slice(
            outcomes,
            "alignment",
            lambda item: item.alignment.value,
        ),
    )


def _slice(
    outcomes: tuple[CalibratedTradeOutcome, ...],
    dimension: str,
    getter: Callable[[CalibratedTradeOutcome], str],
) -> tuple[CalibrationSlice, ...]:
    values = sorted({getter(item) for item in outcomes})
    return tuple(
        CalibrationSlice(
            dimension=dimension,
            value=value,
            metrics=calculate_calibration_metrics(
                tuple(item for item in outcomes if getter(item) == value)
            ),
        )
        for value in values
    )


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _mean(values: tuple[float, ...]) -> float | None:
    return fmean(values) if values else None


__all__ = [
    "AlignmentClass",
    "CalibratedTradeOutcome",
    "CalibrationMetrics",
    "CalibrationReport",
    "CalibrationSlice",
    "OutcomeState",
    "build_calibration_report",
    "calculate_calibration_metrics",
]
