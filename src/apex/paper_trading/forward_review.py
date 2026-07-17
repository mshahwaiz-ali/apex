"""Deterministic forward-validation deviation, lifecycle-audit, and review artifacts."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from apex.backtesting import HistoricalEdgeProfile
from apex.paper_trading.contracts import PaperTrade, PaperTradeState, TERMINAL_STATES
from apex.paper_trading.forward_edge_contracts import (
    ForwardPaperEdgeProfile,
    ForwardPaperValidationResult,
    ForwardPaperValidationStatus,
)

FORWARD_PAPER_REVIEW_SCHEMA_VERSION = 1


class DeviationCompatibilityStatus(StrEnum):
    COMPATIBLE = "COMPATIBLE"
    SEGMENT_MISMATCH = "SEGMENT_MISMATCH"
    DEGRADED = "DEGRADED"


class LifecycleAnomalyCode(StrEnum):
    MISSING_REQUIRED_EVENT = "MISSING_REQUIRED_EVENT"
    INVALID_EVENT_ORDER = "INVALID_EVENT_ORDER"
    TERMINAL_WITHOUT_CLOSE = "TERMINAL_WITHOUT_CLOSE"
    ENTERED_AFTER_INVALIDATION = "ENTERED_AFTER_INVALIDATION"
    EXIT_EVENT_BEFORE_ENTRY = "EXIT_EVENT_BEFORE_ENTRY"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    CLOSED_PERCENTAGE_INCONSISTENT = "CLOSED_PERCENTAGE_INCONSISTENT"
    DUPLICATE_UNIQUE_EVENT = "DUPLICATE_UNIQUE_EVENT"
    HOLDING_LIMIT_EXCEEDED = "HOLDING_LIMIT_EXCEEDED"
    MANAGEMENT_CONTRADICTION = "MANAGEMENT_CONTRADICTION"


class P1ReviewState(StrEnum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    FAILED_VALIDATION = "FAILED_VALIDATION"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    FORWARD_VALIDATED = "FORWARD_VALIDATED"
    NOT_PRODUCTION_ELIGIBLE = "NOT_PRODUCTION_ELIGIBLE"


@dataclass(frozen=True, slots=True)
class ForwardDeviationPolicy:
    maximum_expectancy_degradation_pct: float = 60.0
    maximum_profit_factor_drop: float = 0.5
    maximum_win_rate_drop: float = 0.15
    maximum_drawdown_increase_r: float = 2.0
    maximum_trade_frequency_deviation_pct: float = 100.0

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ForwardDeviationReport:
    dimensions: Mapping[str, str]
    historical_sample_count: int
    forward_sample_count: int
    expectancy_delta: float
    expectancy_degradation_pct: float | None
    profit_factor_delta: float | None
    win_rate_delta: float
    drawdown_delta: float
    trade_frequency_deviation_pct: float
    direction_consistent: bool
    compatibility_status: DeviationCompatibilityStatus
    warnings: tuple[str, ...] = field(default_factory=tuple)
    rejection_reasons: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class LifecycleAnomaly:
    trade_id: str
    code: LifecycleAnomalyCode
    message: str


@dataclass(frozen=True, slots=True)
class LifecycleAuditReport:
    audited_trade_count: int
    anomalies: tuple[LifecycleAnomaly, ...]

    @property
    def passed(self) -> bool:
        return not self.anomalies


@dataclass(frozen=True, slots=True)
class ForwardPaperReviewReport:
    payload: dict[str, Any]
    report_sha256: str


def compare_historical_to_forward(
    historical: HistoricalEdgeProfile,
    forward: ForwardPaperEdgeProfile,
    *,
    historical_period_days: int,
    forward_period_days: int,
    policy: ForwardDeviationPolicy | None = None,
) -> ForwardDeviationReport:
    """Compare strictly compatible historical and forward-paper segments."""
    if dict(historical.dimensions) != dict(forward.dimensions):
        raise ValueError("historical and forward segment dimensions must match exactly")
    if historical_period_days < 1 or forward_period_days < 1:
        raise ValueError("comparison periods must be positive")
    active = policy or ForwardDeviationPolicy()
    expectancy_delta = forward.expectancy - historical.expectancy
    degradation = None
    if historical.expectancy > 0.0:
        degradation = ((historical.expectancy - forward.expectancy) / historical.expectancy) * 100.0
    pf_delta = None
    if historical.profit_factor is not None and forward.profit_factor is not None:
        pf_delta = forward.profit_factor - historical.profit_factor
    win_delta = forward.win_rate - historical.win_rate
    drawdown_delta = forward.maximum_drawdown_r - historical.maximum_drawdown_r
    historical_daily = historical.sample_size / historical_period_days
    forward_daily = forward.sample_size / forward_period_days
    frequency_deviation = abs(forward_daily - historical_daily) / historical_daily * 100.0
    direction_consistent = historical.expectancy == 0.0 or (
        (historical.expectancy > 0.0) == (forward.expectancy > 0.0)
    )
    reasons: list[str] = []
    if degradation is not None and degradation > active.maximum_expectancy_degradation_pct:
        reasons.append("EXPECTANCY_DEGRADATION_EXCESSIVE")
    if pf_delta is not None and pf_delta < -active.maximum_profit_factor_drop:
        reasons.append("PROFIT_FACTOR_DEGRADATION_EXCESSIVE")
    if win_delta < -active.maximum_win_rate_drop:
        reasons.append("WIN_RATE_DEGRADATION_EXCESSIVE")
    if drawdown_delta > active.maximum_drawdown_increase_r:
        reasons.append("DRAWDOWN_INCREASE_EXCESSIVE")
    if frequency_deviation > active.maximum_trade_frequency_deviation_pct:
        reasons.append("TRADE_FREQUENCY_DEVIATION_EXCESSIVE")
    if not direction_consistent:
        reasons.append("EDGE_DIRECTION_INCONSISTENT")
    status = DeviationCompatibilityStatus.DEGRADED if reasons else DeviationCompatibilityStatus.COMPATIBLE
    return ForwardDeviationReport(
        dimensions=dict(historical.dimensions),
        historical_sample_count=historical.sample_size,
        forward_sample_count=forward.sample_size,
        expectancy_delta=expectancy_delta,
        expectancy_degradation_pct=degradation,
        profit_factor_delta=pf_delta,
        win_rate_delta=win_delta,
        drawdown_delta=drawdown_delta,
        trade_frequency_deviation_pct=frequency_deviation,
        direction_consistent=direction_consistent,
        compatibility_status=status,
        warnings=("Production eligibility is not determined by this comparison.",),
        rejection_reasons=tuple(reasons),
    )


def audit_paper_trade_lifecycle(
    trades: Sequence[PaperTrade],
    *,
    maximum_holding_candles: int,
) -> LifecycleAuditReport:
    """Inspect trades without modifying them."""
    if maximum_holding_candles < 1:
        raise ValueError("maximum holding candles must be positive")
    anomalies: list[LifecycleAnomaly] = []
    for trade in sorted(trades, key=lambda item: item.trade_id):
        parsed: list[tuple[str, datetime, Mapping[str, Any]]] = []
        for event in trade.lifecycle_events:
            raw_time = event.get("occurred_at")
            try:
                occurred = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
            except ValueError:
                anomalies.append(LifecycleAnomaly(trade.trade_id, LifecycleAnomalyCode.INVALID_TIMESTAMP, "event timestamp is invalid"))
                continue
            if occurred.tzinfo is None or occurred.utcoffset() is None or occurred < trade.created_at:
                anomalies.append(LifecycleAnomaly(trade.trade_id, LifecycleAnomalyCode.INVALID_TIMESTAMP, "event timestamp is naive or precedes trade creation"))
                continue
            parsed.append((str(event.get("event_type", "")).upper(), occurred, event))
        if [item[1] for item in parsed] != sorted(item[1] for item in parsed):
            anomalies.append(LifecycleAnomaly(trade.trade_id, LifecycleAnomalyCode.INVALID_EVENT_ORDER, "lifecycle events are not chronological"))
        names = [item[0] for item in parsed]
        for unique in ("CREATED", "ENTERED", "STOPPED", "TARGET_HIT", "EXPIRED", "CANCELLED", "INVALIDATED"):
            if names.count(unique) > 1:
                anomalies.append(LifecycleAnomaly(trade.trade_id, LifecycleAnomalyCode.DUPLICATE_UNIQUE_EVENT, f"duplicate {unique} event"))
        if "CREATED" not in names:
            anomalies.append(LifecycleAnomaly(trade.trade_id, LifecycleAnomalyCode.MISSING_REQUIRED_EVENT, "CREATED event is missing"))
        terminal_names = {"STOPPED", "TARGET_HIT", "EXPIRED", "CANCELLED", "INVALIDATED", "CLOSED"}
        if trade.state in TERMINAL_STATES and not terminal_names.intersection(names):
            anomalies.append(LifecycleAnomaly(trade.trade_id, LifecycleAnomalyCode.TERMINAL_WITHOUT_CLOSE, "terminal trade lacks a valid close event"))
        entered_indexes = [index for index, name in enumerate(names) if name == "ENTERED"]
        invalidated_indexes = [index for index, name in enumerate(names) if name == "INVALIDATED"]
        if entered_indexes and invalidated_indexes and entered_indexes[0] > invalidated_indexes[0]:
            anomalies.append(LifecycleAnomaly(trade.trade_id, LifecycleAnomalyCode.ENTERED_AFTER_INVALIDATION, "trade entered after invalidation"))
        for exit_name in ("STOPPED", "TARGET_HIT", "PARTIALLY_CLOSED"):
            if exit_name in names and (not entered_indexes or names.index(exit_name) < entered_indexes[0]):
                anomalies.append(LifecycleAnomaly(trade.trade_id, LifecycleAnomalyCode.EXIT_EVENT_BEFORE_ENTRY, f"{exit_name} occurred before entry"))
        if trade.state in TERMINAL_STATES and trade.closed_percentage != 100.0:
            anomalies.append(LifecycleAnomaly(trade.trade_id, LifecycleAnomalyCode.CLOSED_PERCENTAGE_INCONSISTENT, "terminal trade is not 100 percent closed"))
        if trade.state is PaperTradeState.PARTIALLY_CLOSED and not 0.0 < trade.closed_percentage < 100.0:
            anomalies.append(LifecycleAnomaly(trade.trade_id, LifecycleAnomalyCode.CLOSED_PERCENTAGE_INCONSISTENT, "partial trade closed percentage is inconsistent"))
        if trade.is_open and trade.candles_held > maximum_holding_candles:
            anomalies.append(LifecycleAnomaly(trade.trade_id, LifecycleAnomalyCode.HOLDING_LIMIT_EXCEEDED, "open trade exceeds configured holding limit"))
        if trade.state is PaperTradeState.WAITING_FOR_ENTRY and trade.entry_time is not None:
            anomalies.append(LifecycleAnomaly(trade.trade_id, LifecycleAnomalyCode.MANAGEMENT_CONTRADICTION, "waiting trade already has an entry time"))
    return LifecycleAuditReport(len(trades), tuple(anomalies))


def build_forward_paper_review_report(
    *,
    generated_at: datetime,
    daily_report_sha256: str,
    forward_validation: ForwardPaperValidationResult,
    deviation: ForwardDeviationReport,
    lifecycle_audit: LifecycleAuditReport,
    sample_sufficient: bool,
    manual_execution_usable: bool,
) -> ForwardPaperReviewReport:
    """Build an immutable forward-validation review while withholding production eligibility."""
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("review generation time must be timezone-aware")
    if not sample_sufficient:
        state = P1ReviewState.INSUFFICIENT_EVIDENCE
    elif not lifecycle_audit.passed or forward_validation.status is ForwardPaperValidationStatus.FAILED_VALIDATION:
        state = P1ReviewState.FAILED_VALIDATION
    elif deviation.compatibility_status is DeviationCompatibilityStatus.DEGRADED or not manual_execution_usable:
        state = P1ReviewState.REQUIRES_REVIEW
    elif forward_validation.status is ForwardPaperValidationStatus.PASSED_VALIDATION:
        state = P1ReviewState.FORWARD_VALIDATED
    else:
        state = P1ReviewState.NOT_PRODUCTION_ELIGIBLE
    payload: dict[str, Any] = {
        "schema_version": FORWARD_PAPER_REVIEW_SCHEMA_VERSION,
        "generated_at": generated_at.astimezone(timezone.utc).isoformat(),
        "daily_report_sha256": daily_report_sha256,
        "forward_validation_status": forward_validation.status.value,
        "deviation": _jsonable(deviation),
        "lifecycle_audit": _jsonable(lifecycle_audit),
        "sample_sufficient": sample_sufficient,
        "manual_execution_usable": manual_execution_usable,
        "review_state": state.value,
        "production_eligible": False,
        "production_eligibility_reason": "P1 forward validation does not authorize real-money production execution.",
    }
    report_hash = _hash_payload(payload)
    payload["report_sha256"] = report_hash
    return ForwardPaperReviewReport(payload, report_hash)


def write_forward_paper_review_report(report: ForwardPaperReviewReport, path: Path, *, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite forward-paper review report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report.payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_and_verify_forward_paper_review_report(path: Path) -> ForwardPaperReviewReport:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("forward-paper review report must be a JSON object")
    payload = cast(dict[str, Any], dict(value))
    report_hash = payload.pop("report_sha256", None)
    if not isinstance(report_hash, str) or _hash_payload(payload) != report_hash:
        raise ValueError("forward-paper review report hash does not match its payload")
    payload["report_sha256"] = report_hash
    return ForwardPaperReviewReport(payload, report_hash)


def _jsonable(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {name: _jsonable(getattr(value, name)) for name in value.__dataclass_fields__}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
