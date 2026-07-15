"""Planning tests for aligned historical dataset campaigns."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from apex.backtesting.aligned_dataset_campaign import (
    AlignedDatasetCampaignPlan,
    load_aligned_dataset_campaign_plan,
    plan_aligned_dataset_campaign,
    write_aligned_dataset_campaign_plan,
)


def _plan(tmp_path: Path) -> AlignedDatasetCampaignPlan:
    return plan_aligned_dataset_campaign(
        campaign_id="BTC ETH aligned",
        symbols=("ETH/USDT", "BTC/USDT"),
        timeframes=("4h", "1m", "5m"),
        provider="BINANCE",
        analysis_start=datetime(2025, 1, 1, tzinfo=UTC),
        analysis_end=datetime(2025, 2, 1, tzinfo=UTC),
        output_directory=tmp_path / "datasets",
        warmup_candles=200,
    )


def test_plan_uses_common_boundaries_and_canonical_matrix(tmp_path: Path) -> None:
    plan = _plan(tmp_path)

    assert plan.campaign_id == "btcethaligned"
    assert plan.symbols == ("BTC/USDT", "ETH/USDT")
    assert plan.timeframes == ("1m", "5m", "4h")
    assert plan.warmup_start == plan.boundaries.analysis_start - timedelta(hours=800)
    assert len(plan.jobs) == 6
    assert tuple((job.symbol, job.timeframe) for job in plan.jobs) == (
        ("BTC/USDT", "1m"),
        ("BTC/USDT", "5m"),
        ("BTC/USDT", "4h"),
        ("ETH/USDT", "1m"),
        ("ETH/USDT", "5m"),
        ("ETH/USDT", "4h"),
    )
    counts = {job.timeframe: job.expected_minimum_candles for job in plan.jobs[:3]}
    assert counts["1m"] > counts["5m"] > counts["4h"]


def test_plan_round_trip_is_stable(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    path = tmp_path / "plan.json"

    write_aligned_dataset_campaign_plan(path, plan)

    assert load_aligned_dataset_campaign_plan(path) == plan


def test_plan_rejects_naive_timestamps(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        plan_aligned_dataset_campaign(
            campaign_id="aligned",
            symbols=("BTC/USDT",),
            timeframes=("1m", "4h"),
            provider="binance",
            analysis_start=datetime(2025, 1, 1),
            analysis_end=datetime(2025, 2, 1, tzinfo=UTC),
            output_directory=tmp_path,
        )


def test_plan_rejects_duplicate_symbols(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unique"):
        plan_aligned_dataset_campaign(
            campaign_id="aligned",
            symbols=("BTC/USDT", " btc/usdt "),
            timeframes=("1m", "4h"),
            provider="binance",
            analysis_start=datetime(2025, 1, 1, tzinfo=UTC),
            analysis_end=datetime(2025, 2, 1, tzinfo=UTC),
            output_directory=tmp_path,
        )
