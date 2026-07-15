"""Operational status inspection for sustained P1 paper validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

from apex.paper_trading.store import PaperTradeStore

_SUPPORTED_MARKETS = ("futures", "spot")


@dataclass(frozen=True, slots=True)
class MarketOperationsStatus:
    """Scheduler and evidence status for one paper market."""

    market_type: str
    open_trade_count: int
    closed_trade_count: int
    lock_exists: bool
    lock_stale: bool
    latest_run_at: datetime | None
    latest_run_age_seconds: float | None
    latest_provider_failure_count: int | None
    log_entry_count: int
    scheduler_fresh: bool


@dataclass(frozen=True, slots=True)
class PaperOperationsStatus:
    """Combined sustained-operation readiness snapshot."""

    generated_at: datetime
    store_path: str
    total_trade_count: int
    daily_report_count: int
    review_report_count: int
    markets: tuple[MarketOperationsStatus, ...]

    @property
    def scheduler_ready(self) -> bool:
        return all(item.scheduler_fresh and not item.lock_stale for item in self.markets)


def build_paper_operations_status(
    *,
    data_dir: Path,
    generated_at: datetime,
    maximum_run_age: timedelta = timedelta(minutes=15),
    stale_lock_after: timedelta = timedelta(minutes=30),
) -> PaperOperationsStatus:
    """Inspect persisted paper trades, scheduler logs, locks, and report artifacts."""

    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("operations status generation time must be timezone-aware")
    if maximum_run_age <= timedelta(0):
        raise ValueError("maximum run age must be positive")
    if stale_lock_after <= timedelta(0):
        raise ValueError("stale lock duration must be positive")

    base = data_dir / "paper_trading"
    store_path = base / "trades.json"
    trades = PaperTradeStore(store_path).load()
    market_statuses: list[MarketOperationsStatus] = []

    for market_type in _SUPPORTED_MARKETS:
        matching = tuple(
            trade
            for trade in trades
            if str(trade.analysis_payload.get("market_type", "futures")).strip().lower()
            == market_type
        )
        log_path = base / "scheduler" / "logs" / f"{market_type}.jsonl"
        lock_path = base / "scheduler" / "locks" / f"{market_type}.lock"
        latest, log_entry_count = _latest_log_entry(log_path)
        latest_run_at = _log_completed_at(latest)
        latest_run_age = (
            (generated_at.astimezone(timezone.utc) - latest_run_at).total_seconds()
            if latest_run_at is not None
            else None
        )
        provider_failures = _provider_failure_count(latest)
        lock_exists = lock_path.exists()
        lock_stale = _lock_is_stale(
            lock_path,
            now=generated_at.astimezone(timezone.utc),
            stale_after=stale_lock_after,
        )
        market_statuses.append(
            MarketOperationsStatus(
                market_type=market_type,
                open_trade_count=sum(trade.is_open for trade in matching),
                closed_trade_count=sum(not trade.is_open for trade in matching),
                lock_exists=lock_exists,
                lock_stale=lock_stale,
                latest_run_at=latest_run_at,
                latest_run_age_seconds=latest_run_age,
                latest_provider_failure_count=provider_failures,
                log_entry_count=log_entry_count,
                scheduler_fresh=(
                    latest_run_age is not None
                    and latest_run_age >= 0.0
                    and latest_run_age <= maximum_run_age.total_seconds()
                ),
            )
        )

    return PaperOperationsStatus(
        generated_at=generated_at.astimezone(timezone.utc),
        store_path=str(store_path),
        total_trade_count=len(trades),
        daily_report_count=_json_file_count(base / "daily"),
        review_report_count=_json_file_count(base / "reviews"),
        markets=tuple(market_statuses),
    )


def _latest_log_entry(path: Path) -> tuple[dict[str, Any] | None, int]:
    try:
        lines = tuple(line for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except FileNotFoundError:
        return None, 0
    if not lines:
        return None, 0
    value: object = json.loads(lines[-1])
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError(f"scheduler log entry must be a JSON object: {path}")
    return cast(dict[str, Any], value), len(lines)


def _log_completed_at(entry: dict[str, Any] | None) -> datetime | None:
    if entry is None:
        return None
    raw = entry.get("completed_at")
    if not isinstance(raw, str):
        return None
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("scheduler completed_at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _provider_failure_count(entry: dict[str, Any] | None) -> int | None:
    if entry is None:
        return None
    runtime = entry.get("runtime")
    if not isinstance(runtime, dict):
        return None
    failures = runtime.get("provider_failures")
    return len(failures) if isinstance(failures, list) else None


def _lock_is_stale(path: Path, *, now: datetime, stale_after: timedelta) -> bool:
    if not path.exists():
        return False
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True
    if not isinstance(value, dict):
        return True
    acquired_raw = value.get("acquired_at")
    if not isinstance(acquired_raw, str):
        return True
    acquired = datetime.fromisoformat(acquired_raw.replace("Z", "+00:00"))
    if acquired.tzinfo is None or acquired.utcoffset() is None:
        return True
    return now - acquired.astimezone(timezone.utc) > stale_after


def _json_file_count(path: Path) -> int:
    try:
        return sum(item.is_file() and item.suffix == ".json" for item in path.iterdir())
    except FileNotFoundError:
        return 0
