from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from apex.paper_trading import (
    PaperCycleAlreadyRunningError,
    PaperTradeStore,
    paper_cycle_lock,
    run_scheduled_paper_cycle,
)


class _Provider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_candles(self, symbol: str, timeframe: str, *, limit: int) -> tuple[object, ...]:
        self.calls.append(symbol)
        return ()


def test_lock_rejects_overlap_and_removes_file_after_release(tmp_path: Path) -> None:
    now = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
    lock_path = tmp_path / "futures.lock"

    with paper_cycle_lock(lock_path, acquired_at=now, stale_after=timedelta(minutes=30)):
        assert lock_path.exists()
        with pytest.raises(PaperCycleAlreadyRunningError):
            with paper_cycle_lock(
                lock_path,
                acquired_at=now + timedelta(minutes=1),
                stale_after=timedelta(minutes=30),
            ):
                pass

    assert not lock_path.exists()


def test_stale_lock_is_replaced(tmp_path: Path) -> None:
    now = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
    lock_path = tmp_path / "spot.lock"
    lock_path.write_text(
        json.dumps({"pid": 1, "acquired_at": (now - timedelta(hours=1)).isoformat()}),
        encoding="utf-8",
    )

    with paper_cycle_lock(lock_path, acquired_at=now, stale_after=timedelta(minutes=30)):
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        assert payload["acquired_at"] == now.isoformat()


def test_scheduled_cycle_appends_structured_log(tmp_path: Path) -> None:
    now = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
    store = PaperTradeStore(tmp_path / "trades.json")
    store.save(())
    log_path = tmp_path / "logs" / "futures.jsonl"

    result = run_scheduled_paper_cycle(
        store=store,
        provider=_Provider(),
        market_type="futures",
        timeframe="5m",
        candle_limit=80,
        lock_path=tmp_path / "locks" / "futures.lock",
        log_path=log_path,
        started_at=now,
    )

    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert result.market_type == "futures"
    assert payload["market_type"] == "futures"
    assert payload["runtime"]["cycle"]["eligible_trade_count"] == 0
    assert not (tmp_path / "locks" / "futures.lock").exists()
