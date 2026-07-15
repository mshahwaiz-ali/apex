from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from apex.application.paper_pipeline import run_locked_paper_pipeline
from apex.paper_trading.intake import IntakeMarketType, IntakeSummary
from apex.paper_trading.scheduler import ScheduledPaperCycleResult


def _summary(market_type: IntakeMarketType) -> IntakeSummary:
    return IntakeSummary(
        market_type=market_type,
        candidates_observed=0,
        accepted=0,
        rejected=0,
        duplicates_skipped=0,
        persistence_failures=0,
        reason_counts={},
        created_trade_ids=(),
        results=(),
    )


def _cycle(market_type: str, started_at: datetime) -> ScheduledPaperCycleResult:
    return ScheduledPaperCycleResult(
        market_type=market_type,
        started_at=started_at,
        completed_at=started_at,
        runtime={},  # type: ignore[arg-type]
        lock_path="cycle.lock",
        log_path="cycle.jsonl",
    )


def test_pipeline_runs_intake_before_cycle_and_writes_audit_log(tmp_path) -> None:
    started_at = datetime.now(UTC) - timedelta(seconds=1)
    order: list[str] = []

    result = run_locked_paper_pipeline(
        market_type=IntakeMarketType.FUTURES,
        data_dir=tmp_path,
        started_at=started_at,
        run_id="run-123",
        run_intake=lambda: (order.append("intake") or _summary(IntakeMarketType.FUTURES)),
        run_cycle=lambda: (order.append("cycle") or _cycle("futures", started_at)),
    )

    assert order == ["intake", "cycle"]
    assert result.market_type is IntakeMarketType.FUTURES
    assert result.run_id == "run-123"
    assert result.completed_at >= result.started_at
    log_path = tmp_path / "paper_trading/scheduler/logs/pipeline-futures.jsonl"
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["run_id"] == "run-123"
    assert payload["outcome"] == "success"
    assert payload["market_type"] == "futures"
    assert payload["intake"]["accepted"] == 0
    assert not (tmp_path / "paper_trading/scheduler/locks/pipeline-futures.lock").exists()


def test_pipeline_writes_failure_audit_before_reraising(tmp_path) -> None:
    started_at = datetime.now(UTC) - timedelta(seconds=1)

    def fail_intake() -> IntakeSummary:
        raise RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        run_locked_paper_pipeline(
            market_type=IntakeMarketType.SPOT,
            data_dir=tmp_path,
            started_at=started_at,
            run_id="run-failed",
            run_intake=fail_intake,
            run_cycle=lambda: _cycle("spot", started_at),
        )

    log_path = tmp_path / "paper_trading/scheduler/logs/pipeline-spot.jsonl"
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run-failed"
    assert payload["outcome"] == "failure"
    assert payload["failed_stage"] == "intake"
    assert payload["error_type"] == "RuntimeError"
    assert payload["error_reason"] == "provider unavailable"


def test_pipeline_rejects_cross_market_intake(tmp_path) -> None:
    started_at = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="intake market type"):
        run_locked_paper_pipeline(
            market_type=IntakeMarketType.FUTURES,
            data_dir=tmp_path,
            started_at=started_at,
            run_intake=lambda: _summary(IntakeMarketType.SPOT),
            run_cycle=lambda: _cycle("futures", started_at),
        )


def test_pipeline_rejects_cross_market_cycle(tmp_path) -> None:
    started_at = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="cycle market type"):
        run_locked_paper_pipeline(
            market_type=IntakeMarketType.FUTURES,
            data_dir=tmp_path,
            started_at=started_at,
            run_intake=lambda: _summary(IntakeMarketType.FUTURES),
            run_cycle=lambda: _cycle("spot", started_at),
        )

    payload = json.loads(
        (tmp_path / "paper_trading/scheduler/logs/pipeline-futures.jsonl").read_text(
            encoding="utf-8"
        )
    )
    assert payload["outcome"] == "failure"
    assert payload["failed_stage"] == "lifecycle"


def test_pipeline_requires_timezone_aware_start(tmp_path) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        run_locked_paper_pipeline(
            market_type=IntakeMarketType.SPOT,
            data_dir=tmp_path,
            started_at=datetime(2026, 7, 16, 12, 0),
            run_intake=lambda: _summary(IntakeMarketType.SPOT),
            run_cycle=lambda: _cycle("spot", datetime(2026, 7, 16, 12, 0, tzinfo=UTC)),
        )


def test_pipeline_rejects_non_positive_stale_lock_duration(tmp_path) -> None:
    started_at = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="stale lock duration"):
        run_locked_paper_pipeline(
            market_type=IntakeMarketType.SPOT,
            data_dir=tmp_path,
            started_at=started_at,
            stale_after=timedelta(0),
            run_intake=lambda: _summary(IntakeMarketType.SPOT),
            run_cycle=lambda: _cycle("spot", started_at),
        )


def test_pipeline_rejects_empty_run_id(tmp_path) -> None:
    started_at = datetime.now(UTC)

    with pytest.raises(ValueError, match="run id"):
        run_locked_paper_pipeline(
            market_type=IntakeMarketType.SPOT,
            data_dir=tmp_path,
            started_at=started_at,
            run_id="   ",
            run_intake=lambda: _summary(IntakeMarketType.SPOT),
            run_cycle=lambda: _cycle("spot", started_at),
        )
