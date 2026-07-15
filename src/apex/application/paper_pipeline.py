"""Scheduler-safe orchestration for paper intake followed by lifecycle advancement."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any
from uuid import uuid4

from apex.paper_trading.intake import IntakeMarketType, IntakeSummary, intake_summary_payload
from apex.paper_trading.scheduler import (
    PaperCycleAlreadyRunningError,
    ScheduledPaperCycleResult,
    paper_cycle_lock,
)

__all__ = [
    "PaperPipelineResult",
    "append_paper_pipeline_failure_log",
    "append_paper_pipeline_log",
    "paper_pipeline_payload",
    "run_locked_paper_pipeline",
]


@dataclass(frozen=True, slots=True)
class PaperPipelineResult:
    """Auditable result of one intake-then-cycle pipeline invocation."""

    run_id: str
    market_type: IntakeMarketType
    started_at: datetime
    completed_at: datetime
    intake: IntakeSummary
    cycle: ScheduledPaperCycleResult
    lock_path: str
    log_path: str
    diagnostics: Mapping[str, Any] | None = None
    lifecycle_analytics: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("pipeline run id cannot be empty")
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
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics or {})))
        object.__setattr__(
            self,
            "lifecycle_analytics",
            MappingProxyType(dict(self.lifecycle_analytics or {})),
        )


def run_locked_paper_pipeline(
    *,
    market_type: IntakeMarketType,
    data_dir: Path,
    started_at: datetime,
    run_intake: Callable[[], IntakeSummary],
    run_cycle: Callable[[], ScheduledPaperCycleResult],
    stale_after: timedelta = timedelta(minutes=30),
    run_id: str | None = None,
    diagnostics: Mapping[str, Any] | None = None,
    build_lifecycle_analytics: Callable[
        [IntakeSummary, ScheduledPaperCycleResult], Mapping[str, Any]
    ]
    | None = None,
) -> PaperPipelineResult:
    """Run intake and lifecycle advancement under one market-specific pipeline lock."""

    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise ValueError("pipeline start time must be timezone-aware")
    if stale_after <= timedelta(0):
        raise ValueError("pipeline stale lock duration must be positive")
    normalized_run_id = (run_id or uuid4().hex).strip()
    if not normalized_run_id:
        raise ValueError("pipeline run id cannot be empty")

    base = data_dir / "paper_trading" / "scheduler"
    lock_path = base / "locks" / f"pipeline-{market_type.value}.lock"
    log_path = base / "logs" / f"pipeline-{market_type.value}.jsonl"
    stage = "lock"
    try:
        with paper_cycle_lock(lock_path, acquired_at=started_at, stale_after=stale_after):
            stage = "intake"
            intake = run_intake()
            if intake.market_type is not market_type:
                raise ValueError("pipeline intake market type does not match requested market")
            stage = "lifecycle"
            cycle = run_cycle()
            if cycle.market_type.strip().lower() != market_type.value:
                raise ValueError("pipeline cycle market type does not match requested market")
            stage = "analytics"
            lifecycle_analytics = (
                {}
                if build_lifecycle_analytics is None
                else dict(build_lifecycle_analytics(intake, cycle))
            )
            result = PaperPipelineResult(
                run_id=normalized_run_id,
                market_type=market_type,
                started_at=started_at.astimezone(UTC),
                completed_at=datetime.now(UTC),
                intake=intake,
                cycle=cycle,
                lock_path=str(lock_path),
                log_path=str(log_path),
                diagnostics=diagnostics,
                lifecycle_analytics=lifecycle_analytics,
            )
            append_paper_pipeline_log(result, log_path)
            return result
    except PaperCycleAlreadyRunningError:
        raise
    except Exception as exc:
        append_paper_pipeline_failure_log(
            path=log_path,
            run_id=normalized_run_id,
            market_type=market_type,
            started_at=started_at,
            failed_at=datetime.now(UTC),
            stage=stage,
            error=exc,
            lock_path=lock_path,
        )
        raise


def append_paper_pipeline_log(result: PaperPipelineResult, path: Path) -> None:
    """Append one structured successful pipeline result to JSONL."""

    _append_json_line(path, paper_pipeline_payload(result))


def append_paper_pipeline_failure_log(
    *,
    path: Path,
    run_id: str,
    market_type: IntakeMarketType,
    started_at: datetime,
    failed_at: datetime,
    stage: str,
    error: Exception,
    lock_path: Path,
) -> None:
    """Append one structured failed pipeline result to JSONL."""

    payload = {
        "schema_version": 3,
        "run_id": run_id,
        "outcome": "failure",
        "market_type": market_type.value,
        "started_at": started_at.astimezone(UTC).isoformat(),
        "completed_at": failed_at.astimezone(UTC).isoformat(),
        "failed_stage": stage,
        "error_type": type(error).__name__,
        "error_reason": str(error),
        "lock_path": str(lock_path),
        "log_path": str(path),
    }
    _append_json_line(path, payload)


def paper_pipeline_payload(result: PaperPipelineResult) -> dict[str, Any]:
    """Return a stable JSON-ready successful pipeline payload."""

    return {
        "schema_version": 3,
        "run_id": result.run_id,
        "outcome": "success",
        "market_type": result.market_type.value,
        "started_at": result.started_at.isoformat(),
        "completed_at": result.completed_at.isoformat(),
        "intake": intake_summary_payload(result.intake),
        "cycle": _jsonable(asdict(result.cycle)),
        "diagnostics": _jsonable(dict(result.diagnostics or {})),
        "lifecycle_analytics": _jsonable(dict(result.lifecycle_analytics or {})),
        "lock_path": result.lock_path,
        "log_path": result.log_path,
    }


def _append_json_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


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
