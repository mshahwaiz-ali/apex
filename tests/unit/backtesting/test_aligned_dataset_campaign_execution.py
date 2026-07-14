"""Execution tests for aligned historical dataset campaigns."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.backtesting.aligned_dataset_campaign import plan_aligned_dataset_campaign
from apex.backtesting.aligned_dataset_campaign_execution import (
    execute_aligned_dataset_campaign,
    load_aligned_dataset_campaign_execution_result,
    verify_aligned_dataset_campaign_execution,
)
from apex.domain.models import Candle


class _RangeProvider:
    name = "binance"

    def __init__(self, *, gap: bool = False) -> None:
        self.gap = gap
        self.calls: list[tuple[str, str, datetime, datetime]] = []

    def fetch_candles_range(
        self,
        symbol: str,
        timeframe: str,
        *,
        start_time: datetime,
        end_time: datetime,
    ) -> list[Candle]:
        self.calls.append((symbol, timeframe, start_time, end_time))
        seconds = {"1h": 3600, "4h": 14400}[timeframe]
        step = timedelta(seconds=seconds)
        candles: list[Candle] = []
        cursor = start_time
        index = 0
        while cursor < end_time:
            if not (self.gap and index == 10):
                candles.append(
                    Candle(
                        symbol=symbol,
                        timeframe=timeframe,
                        open_time=cursor,
                        close_time=cursor + step,
                        open=100.0,
                        high=102.0,
                        low=99.0,
                        close=101.0,
                        volume=10.0,
                        is_closed=True,
                        source=self.name,
                    )
                )
            cursor += step
            index += 1
        return candles


def _plan(tmp_path: Path):
    return plan_aligned_dataset_campaign(
        campaign_id="aligned",
        symbols=("BTC/USDT",),
        timeframes=("1h", "4h"),
        provider="binance",
        analysis_start=datetime(2025, 1, 10, tzinfo=UTC),
        analysis_end=datetime(2025, 1, 20, tzinfo=UTC),
        output_directory=tmp_path / "datasets",
        warmup_candles=40,
    )


def test_execution_uses_exact_common_range_and_round_trips(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    provider = _RangeProvider()
    plan_path = tmp_path / "plan.json"
    manifest_path = tmp_path / "execution.json"

    result = execute_aligned_dataset_campaign(
        plan=plan,
        provider=provider,
        plan_path=plan_path,
        execution_manifest_path=manifest_path,
        extracted_at=datetime(2025, 1, 21, tzinfo=UTC),
    )
    loaded = load_aligned_dataset_campaign_execution_result(manifest_path)
    verify_aligned_dataset_campaign_execution(plan=plan, result=loaded)

    assert loaded == result
    assert len(result.jobs) == 2
    assert provider.calls == [
        ("BTC/USDT", "1h", plan.warmup_start, plan.boundaries.analysis_end),
        ("BTC/USDT", "4h", plan.warmup_start, plan.boundaries.analysis_end),
    ]
    assert all(job.warmup_candle_count >= 40 for job in result.jobs)
    assert all(Path(job.dataset_path).exists() for job in result.jobs)


def test_execution_rejects_candle_gaps_and_cleans_outputs(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    manifest_path = tmp_path / "execution.json"

    with pytest.raises(ValueError, match="candle gap"):
        execute_aligned_dataset_campaign(
            plan=plan,
            provider=_RangeProvider(gap=True),
            plan_path=tmp_path / "plan.json",
            execution_manifest_path=manifest_path,
            extracted_at=datetime(2025, 1, 21, tzinfo=UTC),
        )

    assert not manifest_path.exists()
    assert not any(Path(job.dataset_path).exists() for job in plan.jobs)


def test_execution_refuses_existing_artifacts(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    existing = Path(plan.jobs[0].dataset_path)
    existing.parent.mkdir(parents=True)
    existing.write_text("reserved", encoding="utf-8")

    with pytest.raises(FileExistsError, match="refuses to overwrite"):
        execute_aligned_dataset_campaign(
            plan=plan,
            provider=_RangeProvider(),
            plan_path=tmp_path / "plan.json",
            execution_manifest_path=tmp_path / "execution.json",
            extracted_at=datetime(2025, 1, 21, tzinfo=UTC),
        )
