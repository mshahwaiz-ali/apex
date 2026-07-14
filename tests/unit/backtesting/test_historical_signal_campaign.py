"""Tests for verified historical signal campaign inputs."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.backtesting.aligned_dataset_campaign import (
    plan_aligned_dataset_campaign,
    write_aligned_dataset_campaign_plan,
)
from apex.backtesting.aligned_dataset_campaign_execution import (
    AlignedDatasetCampaignExecutionResult,
    AlignedDatasetCampaignJobResult,
    write_aligned_dataset_campaign_execution_result,
)
from apex.backtesting.dataset import (
    build_futures_dataset,
    write_futures_dataset,
)
from apex.backtesting.historical_signal_campaign import (
    load_historical_signal_campaign_inputs,
)
from apex.domain.models import Candle


def _candles(
    *,
    start: datetime,
    count: int,
) -> tuple[Candle, ...]:
    values: list[Candle] = []
    for index in range(count):
        open_time = start + timedelta(minutes=index)
        values.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="1m",
                open_time=open_time,
                close_time=(
                    open_time
                    + timedelta(minutes=1)
                    - timedelta(milliseconds=1)
                ),
                open=100.0 + index,
                high=101.0 + index,
                low=99.0 + index,
                close=100.5 + index,
                volume=10.0 + index,
                is_closed=True,
                source="binance",
            )
        )
    return tuple(values)


def _write_campaign(
    tmp_path: Path,
) -> tuple[Path, Path, Path]:
    analysis_start = datetime(
        2026,
        6,
        1,
        0,
        40,
        tzinfo=UTC,
    )
    analysis_end = datetime(
        2026,
        6,
        1,
        1,
        0,
        tzinfo=UTC,
    )
    dataset_directory = tmp_path / "aligned"
    plan_path = tmp_path / "plan.json"
    execution_path = tmp_path / "execution.json"

    plan = plan_aligned_dataset_campaign(
        campaign_id="verified-pilot",
        symbols=("BTC/USDT",),
        timeframes=("1m",),
        provider="binance",
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        output_directory=dataset_directory,
        warmup_candles=40,
    )
    write_aligned_dataset_campaign_plan(plan_path, plan)

    job = plan.jobs[0]
    candles = _candles(
        start=plan.warmup_start,
        count=60,
    )
    dataset = build_futures_dataset(
        dataset_id=job.dataset_id,
        candles=candles,
        extracted_at=datetime(
            2026,
            7,
            1,
            tzinfo=UTC,
        ),
    )
    dataset_path = Path(job.dataset_path)
    write_futures_dataset(dataset_path, dataset)

    execution = AlignedDatasetCampaignExecutionResult(
        campaign_id=plan.campaign_id,
        provider=plan.provider,
        plan_path=plan_path.as_posix(),
        warmup_start=plan.warmup_start,
        analysis_start=plan.boundaries.analysis_start,
        train_end=plan.boundaries.train_end,
        validation_end=plan.boundaries.validation_end,
        analysis_end=plan.boundaries.analysis_end,
        jobs=(
            AlignedDatasetCampaignJobResult(
                acquisition_order=job.acquisition_order,
                symbol=job.symbol,
                timeframe=job.timeframe,
                dataset_id=job.dataset_id,
                dataset_path=job.dataset_path,
                content_hash=dataset.manifest.content_hash,
                candle_count=dataset.manifest.candle_count,
                warmup_candle_count=40,
                first_open_time=dataset.manifest.start_time,
                last_close_time=dataset.manifest.end_time,
            ),
        ),
    )
    write_aligned_dataset_campaign_execution_result(
        execution_path,
        execution,
    )
    return plan_path, execution_path, dataset_path


def test_loads_verified_campaign_and_preserves_boundaries(
    tmp_path: Path,
) -> None:
    plan_path, execution_path, _ = _write_campaign(tmp_path)

    inputs = load_historical_signal_campaign_inputs(
        plan_path=plan_path,
        execution_manifest_path=execution_path,
    )

    assert inputs.campaign_id == "verifiedpilot"
    assert inputs.provider == "binance"
    assert inputs.symbols == ("BTC/USDT",)
    assert inputs.timeframes == ("1m",)
    assert (
        inputs.boundaries.analysis_start
        == datetime(2026, 6, 1, 0, 40, tzinfo=UTC)
    )
    assert (
        inputs.boundaries.analysis_end
        == datetime(2026, 6, 1, 1, 0, tzinfo=UTC)
    )
    assert inputs.store.symbols == ("BTC/USDT",)
    assert inputs.store.timeframes_for("BTC/USDT") == ("1m",)


def test_source_dataset_references_are_deterministic(
    tmp_path: Path,
) -> None:
    plan_path, execution_path, _ = _write_campaign(tmp_path)

    first = load_historical_signal_campaign_inputs(
        plan_path=plan_path,
        execution_manifest_path=execution_path,
    )
    second = load_historical_signal_campaign_inputs(
        plan_path=plan_path,
        execution_manifest_path=execution_path,
    )

    assert first.source_datasets == second.source_datasets
    assert first.source_dataset_hashes == second.source_dataset_hashes
    assert len(first.source_dataset_hashes) == 1
    assert len(first.source_dataset_hashes[0]) == 64


def test_rejects_execution_manifest_for_different_plan(
    tmp_path: Path,
) -> None:
    plan_path, execution_path, _ = _write_campaign(tmp_path)
    payload = json.loads(
        execution_path.read_text(encoding="utf-8")
    )
    payload["plan_path"] = (
        tmp_path / "different-plan.json"
    ).as_posix()
    execution_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="does not reference the supplied plan",
    ):
        load_historical_signal_campaign_inputs(
            plan_path=plan_path,
            execution_manifest_path=execution_path,
        )


def test_rejects_tampered_dataset_candle_content(
    tmp_path: Path,
) -> None:
    plan_path, execution_path, dataset_path = _write_campaign(
        tmp_path
    )
    payload = json.loads(
        dataset_path.read_text(encoding="utf-8")
    )
    payload["candles"][0]["close"] = 777.0
    payload["candles"][0]["high"] = 778.0
    dataset_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="content hash does not match candles",
    ):
        load_historical_signal_campaign_inputs(
            plan_path=plan_path,
            execution_manifest_path=execution_path,
        )


def test_rejects_execution_dataset_hash_mismatch(
    tmp_path: Path,
) -> None:
    plan_path, execution_path, _ = _write_campaign(tmp_path)
    payload = json.loads(
        execution_path.read_text(encoding="utf-8")
    )
    payload["jobs"][0]["content_hash"] = "0" * 64
    execution_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="persisted dataset hash does not match manifest",
    ):
        load_historical_signal_campaign_inputs(
            plan_path=plan_path,
            execution_manifest_path=execution_path,
        )


def test_rejects_dataset_provider_mismatch(
    tmp_path: Path,
) -> None:
    plan_path, execution_path, dataset_path = _write_campaign(
        tmp_path
    )
    payload = json.loads(
        dataset_path.read_text(encoding="utf-8")
    )
    payload["manifest"]["source"] = "other-provider"
    for candle in payload["candles"]:
        candle["source"] = "other-provider"

    from apex.backtesting.dataset import hash_candles
    from apex.domain.models import Candle

    rebuilt = tuple(
        Candle.model_validate(item)
        for item in payload["candles"]
    )
    payload["manifest"]["content_hash"] = hash_candles(rebuilt)
    dataset_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    execution_payload = json.loads(
        execution_path.read_text(encoding="utf-8")
    )
    execution_payload["jobs"][0]["content_hash"] = (
        payload["manifest"]["content_hash"]
    )
    execution_path.write_text(
        json.dumps(execution_payload),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="provider does not match campaign plan",
    ):
        load_historical_signal_campaign_inputs(
            plan_path=plan_path,
            execution_manifest_path=execution_path,
        )
