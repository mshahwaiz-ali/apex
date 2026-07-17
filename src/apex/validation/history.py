"""Persistent daily forward-validation history."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from apex.paper_trading import PaperTrade
from apex.validation.forward import ForwardValidationReport


@dataclass(frozen=True, slots=True)
class DailyValidationRecord:
    """One date-keyed forward-validation snapshot."""

    trading_date: date
    generated_at: datetime
    report: ForwardValidationReport
    closed_trades_by_strategy: dict[str, int]

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("daily validation generation time must be timezone-aware")
        invalid_counts = any(
            not key.strip() or value < 0 for key, value in self.closed_trades_by_strategy.items()
        )
        if invalid_counts:
            raise ValueError(
                "strategy sample counts require non-empty names and non-negative values"
            )


class DailyValidationStore:
    """JSON store that replaces records by trading date and keeps chronological order."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> tuple[DailyValidationRecord, ...]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return ()
        if not isinstance(payload, list):
            raise ValueError("daily validation store must contain a list")
        return tuple(_record_from_payload(item) for item in payload)

    def upsert(self, record: DailyValidationRecord) -> tuple[DailyValidationRecord, ...]:
        records = tuple(item for item in self.load() if item.trading_date != record.trading_date)
        updated = tuple(sorted((*records, record), key=lambda item: item.trading_date))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([_jsonable(asdict(item)) for item in updated], indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        return updated


def closed_trades_by_strategy(trades: tuple[PaperTrade, ...]) -> dict[str, int]:
    """Count terminal paper samples by canonical strategy name."""

    counts: dict[str, int] = {}
    for trade in trades:
        if trade.is_open:
            continue
        strategy = trade.signal.strategy.value
        counts[strategy] = counts.get(strategy, 0) + 1
    return dict(sorted(counts.items()))


def strategy_sample_shortfalls(
    counts: dict[str, int],
    *,
    minimum_per_strategy: int,
) -> dict[str, int]:
    """Return additional samples required for every observed strategy below threshold."""

    if minimum_per_strategy < 1:
        raise ValueError("minimum per-strategy sample must be positive")
    return {
        strategy: minimum_per_strategy - count
        for strategy, count in sorted(counts.items())
        if count < minimum_per_strategy
    }


def _record_from_payload(value: Any) -> DailyValidationRecord:
    if not isinstance(value, dict):
        raise ValueError("daily validation records must be mappings")
    report_value = value["report"]
    if not isinstance(report_value, dict):
        raise ValueError("daily validation report must be a mapping")
    from apex.validation.forward import ProductionEligibility, ValidationReason

    report = ForwardValidationReport(
        schema_version=int(report_value["schema_version"]),
        generated_at=datetime.fromisoformat(str(report_value["generated_at"])),
        eligibility=ProductionEligibility(str(report_value["eligibility"])),
        reasons=tuple(ValidationReason(str(item)) for item in report_value.get("reasons", [])),
        closed_paper_trades=int(report_value["closed_paper_trades"]),
        modeled_trades=int(report_value["modeled_trades"]),
        win_rate_deviation=float(report_value["win_rate_deviation"]),
        expectancy_deviation=float(report_value["expectancy_deviation"]),
        drawdown_increase=float(report_value["drawdown_increase"]),
    )
    counts_value = value.get("closed_trades_by_strategy", {})
    if not isinstance(counts_value, dict):
        raise ValueError("strategy sample counts must be a mapping")
    return DailyValidationRecord(
        trading_date=date.fromisoformat(str(value["trading_date"])),
        generated_at=datetime.fromisoformat(str(value["generated_at"])),
        report=report,
        closed_trades_by_strategy={str(key): int(count) for key, count in counts_value.items()},
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value
