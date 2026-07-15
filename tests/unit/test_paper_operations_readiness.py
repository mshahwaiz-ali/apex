from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from apex.paper_trading.operations_status import build_paper_operations_status


def _write_log(path, completed_at: datetime, payload: dict[str, object] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {"completed_at": completed_at.isoformat(), **(payload or {})}
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def test_operations_ready_requires_cycle_intake_and_pipeline_freshness(tmp_path) -> None:
    now = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    scheduler = tmp_path / "paper_trading/scheduler"
    for market in ("futures", "spot"):
        _write_log(
            scheduler / "logs" / f"{market}.jsonl",
            now - timedelta(minutes=1),
            {"runtime": {"provider_failures": []}},
        )
        _write_log(scheduler / f"intake-{market}.jsonl", now - timedelta(minutes=1))
        _write_log(
            scheduler / "logs" / f"pipeline-{market}.jsonl",
            now - timedelta(minutes=1),
        )

    status = build_paper_operations_status(data_dir=tmp_path, generated_at=now)

    assert status.scheduler_ready
    assert status.operations_ready
    assert all(item.operationally_ready for item in status.markets)


def test_missing_pipeline_log_keeps_scheduler_ready_but_blocks_operations(tmp_path) -> None:
    now = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    scheduler = tmp_path / "paper_trading/scheduler"
    for market in ("futures", "spot"):
        _write_log(
            scheduler / "logs" / f"{market}.jsonl",
            now,
            {"runtime": {"provider_failures": []}},
        )
        _write_log(scheduler / f"intake-{market}.jsonl", now)

    status = build_paper_operations_status(data_dir=tmp_path, generated_at=now)

    assert status.scheduler_ready
    assert not status.operations_ready
    assert all(not item.pipeline_fresh for item in status.markets)
