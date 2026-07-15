"""Scheduler-safe wrapper for provider-backed paper cycles."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from apex.paper_trading.contracts import PaperTradeConfig
from apex.paper_trading.runtime import (
    CandleProvider,
    PaperRuntimeResult,
    run_provider_backed_paper_cycle,
)
from apex.paper_trading.store import PaperTradeStore


class PaperCycleAlreadyRunningError(RuntimeError):
    """Raised when a non-stale scheduler lock already exists."""


@dataclass(frozen=True, slots=True)
class ScheduledPaperCycleResult:
    """Outcome of one scheduler-safe paper cycle invocation."""

    market_type: str
    started_at: datetime
    completed_at: datetime
    runtime: PaperRuntimeResult
    lock_path: str
    log_path: str


@contextmanager
def paper_cycle_lock(
    path: Path,
    *,
    acquired_at: datetime,
    stale_after: timedelta,
) -> Iterator[None]:
    """Acquire an exclusive lock file and remove it after the cycle finishes."""

    if acquired_at.tzinfo is None or acquired_at.utcoffset() is None:
        raise ValueError("lock acquisition time must be timezone-aware")
    if stale_after <= timedelta(0):
        raise ValueError("lock stale duration must be positive")

    path.parent.mkdir(parents=True, exist_ok=True)
    _remove_stale_lock(path, now=acquired_at, stale_after=stale_after)
    payload = {
        "pid": os.getpid(),
        "acquired_at": acquired_at.astimezone(timezone.utc).isoformat(),
    }
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise PaperCycleAlreadyRunningError(f"paper cycle lock already exists: {path}") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
        yield
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def run_scheduled_paper_cycle(
    *,
    store: PaperTradeStore,
    provider: CandleProvider,
    market_type: str,
    timeframe: str,
    candle_limit: int,
    lock_path: Path,
    log_path: Path,
    started_at: datetime,
    completed_at: datetime | None = None,
    stale_lock_after: timedelta = timedelta(minutes=30),
    config: PaperTradeConfig | None = None,
) -> ScheduledPaperCycleResult:
    """Run one provider-backed cycle with overlap prevention and JSONL logging."""

    with paper_cycle_lock(lock_path, acquired_at=started_at, stale_after=stale_lock_after):
        runtime = run_provider_backed_paper_cycle(
            store=store,
            provider=provider,
            market_type=market_type,
            timeframe=timeframe,
            candle_limit=candle_limit,
            started_at=started_at,
            completed_at=completed_at,
            config=config,
        )
        finished = completed_at or started_at
        result = ScheduledPaperCycleResult(
            market_type=runtime.cycle.market_type,
            started_at=started_at.astimezone(timezone.utc),
            completed_at=finished.astimezone(timezone.utc),
            runtime=runtime,
            lock_path=str(lock_path),
            log_path=str(log_path),
        )
        append_scheduled_paper_cycle_log(result, log_path)
        return result


def append_scheduled_paper_cycle_log(
    result: ScheduledPaperCycleResult,
    path: Path,
) -> None:
    """Append one structured scheduler result to a JSONL file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_jsonable(asdict(result)), sort_keys=True) + "\n")


def _remove_stale_lock(path: Path, *, now: datetime, stale_after: timedelta) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    except (json.JSONDecodeError, OSError):
        payload = {}
    acquired_raw = payload.get("acquired_at") if isinstance(payload, dict) else None
    try:
        acquired = datetime.fromisoformat(str(acquired_raw).replace("Z", "+00:00"))
    except ValueError:
        acquired = None
    if acquired is not None and acquired.tzinfo is not None and acquired.utcoffset() is not None:
        if now - acquired <= stale_after:
            return
    path.unlink(missing_ok=True)


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
