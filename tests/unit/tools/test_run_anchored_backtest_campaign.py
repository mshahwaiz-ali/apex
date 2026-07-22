from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from tools.run_anchored_backtest_campaign import (
    PROFILES,
    SYMBOLS,
    build_jobs,
    default_anchors,
    parse_anchor,
)


def test_default_campaign_has_216_jobs(tmp_path: Path) -> None:
    anchors = default_anchors(datetime(2026, 7, 22, 16, 7, tzinfo=UTC))
    jobs = build_jobs(anchors=anchors, output_dir=tmp_path)

    assert len(anchors) == 4
    assert len(jobs) == 216
    assert len(jobs) == len(SYMBOLS) * len(PROFILES) * len(anchors)


def test_default_anchors_are_completed_and_24_hours_apart() -> None:
    anchors = default_anchors(datetime(2026, 7, 22, 16, 7, tzinfo=UTC))

    assert anchors[0] == datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
    assert tuple((anchors[index] - anchors[index + 1]).total_seconds() for index in range(3)) == (
        86_400.0,
        86_400.0,
        86_400.0,
    )


def test_job_paths_are_unique_and_logs_are_separate(tmp_path: Path) -> None:
    jobs = build_jobs(
        anchors=(datetime(2026, 7, 22, 16, tzinfo=UTC),),
        output_dir=tmp_path,
    )

    assert len({job.report_path for job in jobs}) == len(jobs)
    assert len({job.log_path for job in jobs}) == len(jobs)
    assert all(job.log_path.parent == tmp_path / "logs" for job in jobs)


def test_parse_anchor_normalizes_to_utc() -> None:
    assert parse_anchor("2026-07-22T21:00:00+05:00") == datetime(
        2026,
        7,
        22,
        16,
        tzinfo=UTC,
    )
