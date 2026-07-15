from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apex.paper_trading import build_paper_operations_status


def test_operations_status_reports_fresh_scheduler_and_artifacts(tmp_path: Path) -> None:
    now = datetime(2026, 7, 16, 12, tzinfo=timezone.utc)
    base = tmp_path / "paper_trading"
    (base / "scheduler" / "logs").mkdir(parents=True)
    (base / "daily").mkdir()
    (base / "reviews").mkdir()
    (base / "trades.json").write_text("[]\n", encoding="utf-8")
    (base / "daily" / "2026-07-16.json").write_text("{}", encoding="utf-8")
    (base / "reviews" / "2026-07-16.json").write_text("{}", encoding="utf-8")

    for market in ("futures", "spot"):
        payload = {
            "completed_at": (now - timedelta(minutes=5)).isoformat(),
            "runtime": {"provider_failures": []},
        }
        (base / "scheduler" / "logs" / f"{market}.jsonl").write_text(
            json.dumps(payload) + "\n",
            encoding="utf-8",
        )

    status = build_paper_operations_status(data_dir=tmp_path, generated_at=now)

    assert status.scheduler_ready
    assert status.total_trade_count == 0
    assert status.daily_report_count == 1
    assert status.review_report_count == 1
    assert all(item.scheduler_fresh for item in status.markets)
    assert all(item.latest_provider_failure_count == 0 for item in status.markets)


def test_operations_status_flags_missing_runs_and_stale_lock(tmp_path: Path) -> None:
    now = datetime(2026, 7, 16, 12, tzinfo=timezone.utc)
    base = tmp_path / "paper_trading"
    lock_dir = base / "scheduler" / "locks"
    lock_dir.mkdir(parents=True)
    (base / "trades.json").write_text("[]\n", encoding="utf-8")
    (lock_dir / "futures.lock").write_text(
        json.dumps({"acquired_at": (now - timedelta(hours=1)).isoformat()}),
        encoding="utf-8",
    )

    status = build_paper_operations_status(data_dir=tmp_path, generated_at=now)
    futures = next(item for item in status.markets if item.market_type == "futures")

    assert not status.scheduler_ready
    assert futures.lock_exists
    assert futures.lock_stale
    assert futures.latest_run_at is None
