"""Tests for deterministic historical dataset campaign execution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.backtesting.dataset_campaign import (
    FuturesDatasetCampaignPlan,
    plan_futures_dataset_campaign,
)
from apex.backtesting.dataset_campaign_execution import (
    FuturesDatasetCampaignExecutionError,
    FuturesDatasetCampaignExecutionStatus,
    execute_futures_dataset_campaign,
    load_futures_dataset_campaign_execution_result,
    verify_futures_dataset_campaign_execution,
    write_futures_dataset_campaign_execution_result,
)
from apex.backtesting.dataset_split import FuturesDatasetSplitRatios
from apex.domain.models import Candle, TickerSnapshot


class FakeProvider:
    def __init__(
        self,
        *,
        fail_symbol: str | None = None,
        source: str = "binance",
    ) -> None:
        self.fail_symbol = fail_symbol
        self.source = source
        self.calls: list[tuple[str, str, int]] = []

    @property
    def name(self) -> str:
        return self.source

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> list[Candle]:
        self.calls.append((symbol, timeframe, limit))
        if symbol == self.fail_symbol:
            raise ValueError(f"synthetic acquisition failure for {symbol}")

        start = datetime(2026, 1, 1, tzinfo=UTC)
        return [
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                open_time=start + timedelta(minutes=5 * index),
                close_time=start + timedelta(minutes=5 * (index + 1)),
                open=100.0 + index,
                high=101.0 + index,
                low=99.0 + index,
                close=100.5 + index,
                volume=1_000.0 + index,
                is_closed=True,
                source=self.source,
            )
            for index in range(limit)
        ]

    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        raise NotImplementedError


def _plan(
    tmp_path: Path,
    symbols: tuple[str, ...] = ("ETH/USDT", "BTC/USDT"),
) -> FuturesDatasetCampaignPlan:
    return plan_futures_dataset_campaign(
        campaign_id="n45-test",
        symbols=symbols,
        timeframe="5m",
        provider="binance",
        candle_count=9,
        output_directory=tmp_path / "datasets",
        split_ratios=FuturesDatasetSplitRatios(
            train=0.60,
            validation=0.20,
            final_test=0.20,
        ),
    )


def test_executes_frozen_order_arguments_ids_paths_and_ratios(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    provider = FakeProvider()
    manifest_path = tmp_path / "execution.json"

    result = execute_futures_dataset_campaign(
        plan=plan,
        provider=provider,
        configured_provider="binance",
        extracted_at=datetime(2026, 1, 2, tzinfo=UTC),
        execution_manifest_path=manifest_path,
    )

    assert provider.calls == [
        ("BTC/USDT", "5m", 9),
        ("ETH/USDT", "5m", 9),
    ]
    assert result.status is FuturesDatasetCampaignExecutionStatus.COMPLETED
    assert result.completed_jobs == 2
    assert result.failed_jobs == 0

    for job, job_result in zip(plan.jobs, result.jobs, strict=True):
        assert job_result.parent is not None
        assert job_result.train is not None
        assert job_result.validation is not None
        assert job_result.final_test is not None
        assert job_result.parent.dataset_id == job.parent_dataset_id
        assert job_result.train.dataset_id == job.train_dataset_id
        assert job_result.validation.dataset_id == job.validation_dataset_id
        assert job_result.final_test.dataset_id == job.final_test_dataset_id
        assert job_result.parent.path == job.parent_dataset_path
        assert job_result.train.path == job.train_dataset_path
        assert job_result.validation.path == job.validation_dataset_path
        assert job_result.final_test.path == job.final_test_dataset_path
        assert job_result.split_manifest_path == job.split_manifest_path
        assert (
            job_result.train.candle_count,
            job_result.validation.candle_count,
            job_result.final_test.candle_count,
        ) == (5, 2, 2)

    verify_futures_dataset_campaign_execution(plan=plan, result=result)


def test_rejects_provider_mismatch_before_acquisition(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    provider = FakeProvider()

    with pytest.raises(ValueError, match="does not match configured provider"):
        execute_futures_dataset_campaign(
            plan=plan,
            provider=provider,
            configured_provider="other",
            extracted_at=datetime(2026, 1, 2, tzinfo=UTC),
            execution_manifest_path=tmp_path / "execution.json",
        )

    assert provider.calls == []


def test_rejects_pre_existing_artifact_before_acquisition(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    existing = Path(plan.jobs[0].parent_dataset_path)
    existing.parent.mkdir(parents=True)
    existing.write_text("{}\n", encoding="utf-8")
    provider = FakeProvider()

    with pytest.raises(FileExistsError, match="refuses to overwrite"):
        execute_futures_dataset_campaign(
            plan=plan,
            provider=provider,
            configured_provider="binance",
            extracted_at=datetime(2026, 1, 2, tzinfo=UTC),
            execution_manifest_path=tmp_path / "execution.json",
        )

    assert provider.calls == []


def test_acquisition_failure_is_fail_fast_and_removes_created_artifacts(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    provider = FakeProvider(fail_symbol="ETH/USDT")
    manifest_path = tmp_path / "execution.json"

    with pytest.raises(FuturesDatasetCampaignExecutionError) as captured:
        execute_futures_dataset_campaign(
            plan=plan,
            provider=provider,
            configured_provider="binance",
            extracted_at=datetime(2026, 1, 2, tzinfo=UTC),
            execution_manifest_path=manifest_path,
        )

    result = captured.value.result
    assert provider.calls == [
        ("BTC/USDT", "5m", 9),
        ("ETH/USDT", "5m", 9),
    ]
    assert result.status is FuturesDatasetCampaignExecutionStatus.FAILED
    assert result.completed_jobs == 1
    assert result.failed_jobs == 1
    assert result.jobs[-1].failure_reason == ("synthetic acquisition failure for ETH/USDT")
    assert not manifest_path.exists()
    assert all(not Path(path).exists() for job in plan.jobs for path in job.artifact_paths())


def test_provider_source_mismatch_fails_without_success_manifest(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path, symbols=("BTC/USDT",))
    manifest_path = tmp_path / "execution.json"

    with pytest.raises(
        FuturesDatasetCampaignExecutionError,
        match="provider does not match",
    ):
        execute_futures_dataset_campaign(
            plan=plan,
            provider=FakeProvider(source="wrong"),
            configured_provider="binance",
            extracted_at=datetime(2026, 1, 2, tzinfo=UTC),
            execution_manifest_path=manifest_path,
        )

    assert not manifest_path.exists()


def test_execution_manifest_round_trip_and_reload_verification(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path, symbols=("BTC/USDT",))
    manifest_path = tmp_path / "execution.json"
    result = execute_futures_dataset_campaign(
        plan=plan,
        provider=FakeProvider(),
        configured_provider="binance",
        extracted_at=datetime(2026, 1, 2, tzinfo=UTC),
        execution_manifest_path=manifest_path,
    )

    write_futures_dataset_campaign_execution_result(manifest_path, result)
    loaded = load_futures_dataset_campaign_execution_result(manifest_path)

    assert loaded == result
    verify_futures_dataset_campaign_execution(plan=plan, result=loaded)


def test_tampered_child_id_is_rejected_on_manifest_load(tmp_path: Path) -> None:
    plan = _plan(tmp_path, symbols=("BTC/USDT",))
    manifest_path = tmp_path / "execution.json"
    result = execute_futures_dataset_campaign(
        plan=plan,
        provider=FakeProvider(),
        configured_provider="binance",
        extracted_at=datetime(2026, 1, 2, tzinfo=UTC),
        execution_manifest_path=manifest_path,
    )
    write_futures_dataset_campaign_execution_result(manifest_path, result)

    text = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(
        text.replace(
            plan.jobs[0].train_dataset_id,
            f"{plan.jobs[0].train_dataset_id}-tampered",
            1,
        ),
        encoding="utf-8",
    )

    loaded = load_futures_dataset_campaign_execution_result(manifest_path)
    with pytest.raises(ValueError, match="artifact ID does not match plan"):
        verify_futures_dataset_campaign_execution(plan=plan, result=loaded)
