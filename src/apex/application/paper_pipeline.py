"""Scheduler-safe orchestration for paper intake followed by lifecycle advancement."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from apex.paper_trading.intake import IntakeMarketType, IntakeSummary, intake_summary_payload
from apex.paper_trading.scheduler import ScheduledPaperCycleResult, paper_cycle_lock

__all__ = [
    "PaperPipelineResult",
    "append_paper_pipeline_log",
    "paper_pipeline_payload",
    "run_locked_paper_pipeline",
]


@dataclass(frozen=True, slots=True)
class PaperPipelineResult:
    """Auditable result of one intake-then-cycle pipeline invocation."""

    market_type: IntakeMarketType
    started_at: datetime
    completed_at: datetime
    intake: IntakeSummary
    cycle: ScheduledPaperCycleResult
    lock_path: str
    log_path: str

    def __post_init__(self) -> None:
        for name in ("started_at", "completed_at"):
            value = getattr(self, name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"pipeline {name.replace('_', ' ')} must be timezone-aware")
        if self.completed_at < self.started_at:
            raise ValueError("pipeline completion cannot precede start")
        if self.intake.market_type is not self.market_type:
            raise ValueError("pipeline intake market type does not match result market")
        if self.cycle.market_type.strip().lower() != self.market_type.value:
            raise ValueError("pipeline cycle market type does not match result market")


def run_locked_paper_pipeline(
    *,
    market_type: IntakeMarketType,
    data_dir: Path,
    started_at: datetime,
    run_intake: Callable[[], IntakeSummary],
    run_cycle: Callable[[], ScheduledPaperCycleResult],
    stale_after: timedelta = timedelta(minutes=30),
) -> PaperPipelineResult:
    """Run intake and lifecycle advancement under one market-specific pipeline lock."""

    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise ValueError("pipeline start time must be timezone-aware")
    if stale_after <= timedelta(0):
        raise ValueError("pipeline stale lock duration must be positive")
    base = data_dir / "paper_trading" / "scheduler"
    lock_path = base / "locks" / f"pipeline-{market_type.value}.lock"
    log_path = base / "logs" / f"pipeline-{market_type.value}.jsonl"
    with paper_cycle_lock(lock_path, acquired_at=started_at, stale_after=stale_after):
        intake = run_intake()
        if intake.market_type is not market_type:
            raise ValueError("pipeline intake market type does not match requested market")
        cycle = run_cycle()
        if cycle.market_type.strip().lower() != market_type.value:
            raise ValueError("pipeline cycle market type does not match requested market")
        result = PaperPipelineResult(
            market_type=market_type,
            started_at=started_at.astimezone(UTC),
            completed_at=datetime.now(UTC),
            intake=intake,
            cycle=cycle,
            lock_path=str(lock_path),
            log_path=str(log_path),
        )
        append_paper_pipeline_log(result, log_path)
        return result


def append_paper_pipeline_log(result: PaperPipelineResult, path: Path) -> None:
    """Append one structured pipeline result to JSONL."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(paper_pipeline_payload(result), sort_keys=True) + "\n")


def paper_pipeline_payload(result: PaperPipelineResult) -> dict[str, Any]:
    """Return a stable JSON-ready pipeline payload."""

    return {
        "market_type": result.market_type.value,
        "started_at": result.started_at.isoformat(),
        "completed_at": result.completed_at.isoformat(),
        "intake": intake_summary_payload(result.intake),
        "cycle": _jsonable(asdict(result.cycle)),
        "lock_path": result.lock_path,
        "log_path": result.log_path,
    }


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
