from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apex.paper_trading.operations_status import build_paper_operations_status


def _write_log(
    path: Path,
    completed_at: datetime,
    payload: dict[str, object] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {"completed_at": completed_at.isoformat(), **(payload or {})}
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _append_log(
    path: Path,
    completed_at: datetime,
    payload: dict[str, object] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {"completed_at": completed_at.isoformat(), **(payload or {})}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value) + "\n")


def _write_fresh_stage_logs(tmp_path: Path, now: datetime) -> None:
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
            {"outcome": "success", "run_id": f"{market}-success"},
        )


def test_operations_ready_requires_cycle_intake_and_pipeline_freshness(tmp_path) -> None:
    now = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    _write_fresh_stage_logs(tmp_path, now)

    status = build_paper_operations_status(data_dir=tmp_path, generated_at=now)

    assert status.scheduler_ready
    assert status.operations_ready
    assert all(item.operationally_ready for item in status.markets)
    assert all(item.latest_pipeline_outcome == "success" for item in status.markets)


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


def test_newer_pipeline_failure_blocks_operations_readiness(tmp_path) -> None:
    now = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    _write_fresh_stage_logs(tmp_path, now)
    pipeline_log = (
        tmp_path / "paper_trading/scheduler/logs/pipeline-futures.jsonl"
    )
    _append_log(
        pipeline_log,
        now,
        {
            "outcome": "failure",
            "run_id": "futures-failed",
            "failed_stage": "intake",
            "error_reason": "provider unavailable",
        },
    )

    status = build_paper_operations_status(data_dir=tmp_path, generated_at=now)
    futures = next(item for item in status.markets if item.market_type == "futures")

    assert status.scheduler_ready
    assert not status.operations_ready
    assert not futures.operationally_ready
    assert futures.latest_pipeline_outcome == "failure"
    assert futures.latest_pipeline_run_id == "futures-failed"
    assert futures.latest_pipeline_failure_stage == "intake"
    assert futures.latest_pipeline_failure_reason == "provider unavailable"
    assert futures.consecutive_pipeline_failures == 1


def test_malformed_log_line_is_reported_without_hiding_latest_valid_entry(tmp_path) -> None:
    now = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    _write_fresh_stage_logs(tmp_path, now)
    pipeline_log = tmp_path / "paper_trading/scheduler/logs/pipeline-spot.jsonl"
    with pipeline_log.open("a", encoding="utf-8") as handle:
        handle.write("{not-json}\n")

    status = build_paper_operations_status(data_dir=tmp_path, generated_at=now)
    spot = next(item for item in status.markets if item.market_type == "spot")

    assert status.operations_ready
    assert spot.latest_pipeline_outcome == "success"
    assert spot.malformed_pipeline_log_count == 1
    assert spot.pipeline_log_entry_count == 1
