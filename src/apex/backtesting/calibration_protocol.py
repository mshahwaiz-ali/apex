"""Leakage-safe calibration protocol and final methodology acceptance gate."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from itertools import pairwise

from apex.backtesting.calibration_acceptance import (
    AcceptanceState,
    CalibrationAcceptancePolicy,
    CalibrationAcceptanceResult,
    evaluate_calibration_acceptance,
)
from apex.backtesting.calibration_metrics import CalibrationReport


class TriggerHandling(StrEnum):
    """How entries are evaluated against historical bars."""

    INTRABAR_CONSERVATIVE = "intrabar_conservative"
    NEXT_BAR = "next_bar"


class PartialTargetModel(StrEnum):
    """Consistent partial-exit accounting model."""

    FIXED_FRACTIONS = "fixed_fractions"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class ChronologicalSplit:
    """One strictly ordered train/validation/test split."""

    train_start: datetime
    train_end: datetime
    validation_start: datetime
    validation_end: datetime
    test_start: datetime
    test_end: datetime

    def __post_init__(self) -> None:
        ordered = (
            self.train_start,
            self.train_end,
            self.validation_start,
            self.validation_end,
            self.test_start,
            self.test_end,
        )
        if any(left >= right for left, right in pairwise(ordered)):
            raise ValueError("chronological split boundaries must be strictly increasing")


@dataclass(frozen=True, slots=True)
class CalibrationProtocol:
    """Rules required for a calibration run to be acceptance-eligible."""

    split: ChronologicalSplit
    future_data_access_disabled: bool
    trigger_handling: TriggerHandling
    entry_zone_respected: bool
    maximum_chase_respected: bool
    fees_included: bool
    slippage_included: bool
    partial_target_model: PartialTargetModel
    missed_trades_preserved: bool
    stale_and_developing_preserved: bool
    sample_size_reported: bool


@dataclass(frozen=True, slots=True)
class EquityObservation:
    """Ordered realized equity observation expressed in R units."""

    timestamp: datetime
    cumulative_r: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.cumulative_r):
            raise ValueError("cumulative_r must be finite")


@dataclass(frozen=True, slots=True)
class ProtocolValidation:
    """Protocol validity and all blocking reasons."""

    valid: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MethodologyAcceptancePolicy:
    """Final acceptance thresholds including drawdown."""

    calibration: CalibrationAcceptancePolicy
    maximum_drawdown_r: float = 10.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.maximum_drawdown_r):
            raise ValueError("maximum_drawdown_r must be finite")
        if self.maximum_drawdown_r < 0:
            raise ValueError("maximum_drawdown_r must be non-negative")


@dataclass(frozen=True, slots=True)
class MethodologyAcceptanceResult:
    """Final methodology result used to gate user-facing claims."""

    state: AcceptanceState
    reasons: tuple[str, ...]
    confidence_claims_allowed: bool
    maximum_drawdown_r: float | None
    protocol_valid: bool
    calibration_result: CalibrationAcceptanceResult


def validate_calibration_protocol(
    protocol: CalibrationProtocol,
) -> ProtocolValidation:
    """Validate all explicit no-leakage and realism requirements."""

    reasons: list[str] = []
    if not protocol.future_data_access_disabled:
        reasons.append("future-data access is not disabled")
    if not protocol.entry_zone_respected:
        reasons.append("entry-zone rules were not respected")
    if not protocol.maximum_chase_respected:
        reasons.append("maximum-chase rules were not respected")
    if not protocol.fees_included:
        reasons.append("fees were not included")
    if not protocol.slippage_included:
        reasons.append("slippage was not included")
    if not protocol.missed_trades_preserved:
        reasons.append("missed trades were not preserved")
    if not protocol.stale_and_developing_preserved:
        reasons.append("stale or developing setups were not preserved")
    if not protocol.sample_size_reported:
        reasons.append("sample size was not reported")

    return ProtocolValidation(valid=not reasons, reasons=tuple(reasons))


def calculate_maximum_drawdown_r(
    observations: tuple[EquityObservation, ...],
) -> float | None:
    """Calculate maximum peak-to-trough drawdown from ordered equity."""

    if not observations:
        return None

    previous_timestamp: datetime | None = None
    peak = -math.inf
    maximum_drawdown = 0.0

    for observation in observations:
        if previous_timestamp is not None and observation.timestamp <= previous_timestamp:
            raise ValueError("equity observations must be strictly chronological")
        previous_timestamp = observation.timestamp
        peak = max(peak, observation.cumulative_r)
        maximum_drawdown = max(
            maximum_drawdown,
            peak - observation.cumulative_r,
        )

    return maximum_drawdown


def evaluate_methodology_acceptance(
    report: CalibrationReport,
    *,
    protocol: CalibrationProtocol,
    equity_curve: tuple[EquityObservation, ...],
    policy: MethodologyAcceptancePolicy,
) -> MethodologyAcceptanceResult:
    """Apply protocol, calibration, and drawdown gates together."""

    protocol_result = validate_calibration_protocol(protocol)
    calibration_result = evaluate_calibration_acceptance(
        report,
        policy=policy.calibration,
    )
    maximum_drawdown = calculate_maximum_drawdown_r(equity_curve)

    reasons = list(protocol_result.reasons)
    reasons.extend(calibration_result.reasons)

    if maximum_drawdown is None:
        reasons.append("drawdown cannot be evaluated without an equity curve")
    elif maximum_drawdown > policy.maximum_drawdown_r:
        reasons.append("maximum drawdown exceeds the configured tolerance")

    if calibration_result.state is AcceptanceState.INSUFFICIENT_SAMPLE:
        state = AcceptanceState.INSUFFICIENT_SAMPLE
    elif reasons:
        state = AcceptanceState.REJECTED
    else:
        state = AcceptanceState.ACCEPTED

    allowed = state is AcceptanceState.ACCEPTED
    return MethodologyAcceptanceResult(
        state=state,
        reasons=tuple(dict.fromkeys(reasons)),
        confidence_claims_allowed=allowed,
        maximum_drawdown_r=maximum_drawdown,
        protocol_valid=protocol_result.valid,
        calibration_result=calibration_result,
    )


__all__ = [
    "CalibrationProtocol",
    "ChronologicalSplit",
    "EquityObservation",
    "MethodologyAcceptancePolicy",
    "MethodologyAcceptanceResult",
    "PartialTargetModel",
    "ProtocolValidation",
    "TriggerHandling",
    "calculate_maximum_drawdown_r",
    "evaluate_methodology_acceptance",
    "validate_calibration_protocol",
]
