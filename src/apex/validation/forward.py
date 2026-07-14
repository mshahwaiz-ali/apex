"""Forward paper-validation contracts and deterministic eligibility evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.backtesting import BacktestReport
from apex.paper_trading import PaperPerformance


class ProductionEligibility(StrEnum):
    """Aggregate forward-validation eligibility state."""

    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    PAPER_ONLY = "PAPER_ONLY"
    READY_FOR_FUNDED_REVIEW = "READY_FOR_FUNDED_REVIEW"
    REJECTED = "REJECTED"


class ValidationReason(StrEnum):
    """Stable machine-readable forward-validation reason codes."""

    MINIMUM_SAMPLE_NOT_MET = "MINIMUM_SAMPLE_NOT_MET"
    CRITICAL_LIFECYCLE_FAILURE = "CRITICAL_LIFECYCLE_FAILURE"
    CRITICAL_RISK_CONTROL_FAILURE = "CRITICAL_RISK_CONTROL_FAILURE"
    WIN_RATE_DEVIATION_EXCEEDED = "WIN_RATE_DEVIATION_EXCEEDED"
    EXPECTANCY_DEVIATION_EXCEEDED = "EXPECTANCY_DEVIATION_EXCEEDED"
    DRAWDOWN_DEVIATION_EXCEEDED = "DRAWDOWN_DEVIATION_EXCEEDED"
    MANUAL_INSTRUCTIONS_UNUSABLE = "MANUAL_INSTRUCTIONS_UNUSABLE"


@dataclass(frozen=True, slots=True)
class ForwardValidationThresholds:
    """Configurable P1 acceptance thresholds."""

    minimum_closed_trades: int = 30
    maximum_win_rate_deviation: float = 0.15
    maximum_expectancy_deviation: float = 0.50
    maximum_drawdown_increase: float = 0.25

    def __post_init__(self) -> None:
        if self.minimum_closed_trades < 1:
            raise ValueError("minimum closed trades must be positive")
        for name in (
            "maximum_win_rate_deviation",
            "maximum_expectancy_deviation",
            "maximum_drawdown_increase",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ForwardValidationEvidence:
    """Observed forward-operation evidence not inferable from aggregate PnL alone."""

    critical_lifecycle_failures: int = 0
    critical_risk_control_failures: int = 0
    manual_instruction_failures: int = 0
    paper_expectancy: float = 0.0
    paper_maximum_drawdown: float = 0.0

    def __post_init__(self) -> None:
        for name in (
            "critical_lifecycle_failures",
            "critical_risk_control_failures",
            "manual_instruction_failures",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name.replace('_', ' ')} cannot be negative")
        for name in ("paper_expectancy", "paper_maximum_drawdown"):
            value = getattr(self, name)
            if not math.isfinite(value):
                raise ValueError(f"{name.replace('_', ' ')} must be finite")
        if self.paper_maximum_drawdown < 0.0:
            raise ValueError("paper maximum drawdown cannot be negative")


@dataclass(frozen=True, slots=True)
class ForwardValidationReport:
    """Schema-versioned P1 production-eligibility review."""

    schema_version: int
    generated_at: datetime
    eligibility: ProductionEligibility
    reasons: tuple[ValidationReason, ...]
    closed_paper_trades: int
    modeled_trades: int
    win_rate_deviation: float
    expectancy_deviation: float
    drawdown_increase: float

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported forward-validation schema version")
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("forward-validation report time must be timezone-aware")
        if self.closed_paper_trades < 0 or self.modeled_trades < 0:
            raise ValueError("validation trade counts cannot be negative")
        for name in ("win_rate_deviation", "expectancy_deviation", "drawdown_increase"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name.replace('_', ' ')} must be finite")


def evaluate_forward_validation(
    *,
    backtest: BacktestReport,
    paper: PaperPerformance,
    evidence: ForwardValidationEvidence,
    thresholds: ForwardValidationThresholds,
    generated_at: datetime,
) -> ForwardValidationReport:
    """Evaluate P1 acceptance without fabricating unavailable operational evidence."""

    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("forward-validation report time must be timezone-aware")

    win_rate_deviation = abs(paper.win_rate - backtest.win_rate)
    expectancy_denominator = max(abs(backtest.expectancy), 1e-9)
    expectancy_deviation = abs(evidence.paper_expectancy - backtest.expectancy) / expectancy_denominator
    drawdown_denominator = max(backtest.maximum_drawdown, 1e-9)
    drawdown_increase = max(
        0.0,
        evidence.paper_maximum_drawdown - backtest.maximum_drawdown,
    ) / drawdown_denominator

    reasons: list[ValidationReason] = []
    if paper.closed_trades < thresholds.minimum_closed_trades:
        reasons.append(ValidationReason.MINIMUM_SAMPLE_NOT_MET)
    if evidence.critical_lifecycle_failures:
        reasons.append(ValidationReason.CRITICAL_LIFECYCLE_FAILURE)
    if evidence.critical_risk_control_failures:
        reasons.append(ValidationReason.CRITICAL_RISK_CONTROL_FAILURE)
    if evidence.manual_instruction_failures:
        reasons.append(ValidationReason.MANUAL_INSTRUCTIONS_UNUSABLE)
    if win_rate_deviation > thresholds.maximum_win_rate_deviation:
        reasons.append(ValidationReason.WIN_RATE_DEVIATION_EXCEEDED)
    if expectancy_deviation > thresholds.maximum_expectancy_deviation:
        reasons.append(ValidationReason.EXPECTANCY_DEVIATION_EXCEEDED)
    if drawdown_increase > thresholds.maximum_drawdown_increase:
        reasons.append(ValidationReason.DRAWDOWN_DEVIATION_EXCEEDED)

    critical_reasons = {
        ValidationReason.CRITICAL_LIFECYCLE_FAILURE,
        ValidationReason.CRITICAL_RISK_CONTROL_FAILURE,
        ValidationReason.MANUAL_INSTRUCTIONS_UNUSABLE,
    }
    if any(reason in critical_reasons for reason in reasons):
        eligibility = ProductionEligibility.REJECTED
    elif ValidationReason.MINIMUM_SAMPLE_NOT_MET in reasons:
        eligibility = ProductionEligibility.INSUFFICIENT_SAMPLE
    elif reasons:
        eligibility = ProductionEligibility.PAPER_ONLY
    else:
        eligibility = ProductionEligibility.READY_FOR_FUNDED_REVIEW

    return ForwardValidationReport(
        schema_version=1,
        generated_at=generated_at,
        eligibility=eligibility,
        reasons=tuple(reasons),
        closed_paper_trades=paper.closed_trades,
        modeled_trades=backtest.total_trades,
        win_rate_deviation=win_rate_deviation,
        expectancy_deviation=expectancy_deviation,
        drawdown_increase=drawdown_increase,
    )
