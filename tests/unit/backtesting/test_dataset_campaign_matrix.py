"""N4.6 deterministic multi-timeframe dataset campaign tests."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from apex.backtesting.dataset_campaign import (
    FUTURES_DATASET_CAMPAIGN_SCHEMA_VERSION,
    FuturesDatasetCampaignPlan,
    load_futures_dataset_campaign_plan,
    normalize_campaign_timeframes,
    plan_futures_dataset_campaign,
    verify_futures_dataset_campaign_matrix,
    write_futures_dataset_campaign_plan,
)
from apex.backtesting.dataset_campaign_execution import (
    execute_futures_dataset_campaign,
    verify_futures_dataset_campaign_execution,
)
from apex.cli_app import app
from apex.domain.models import Candle

runner = CliRunner()


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> list[Candle]:
        self.calls.append((symbol, timeframe, limit))
        start = datetime(2026, 1, 1, tzinfo=UTC)
        minutes = {
            "1m": 1,
            "3m": 3,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
        }[timeframe]
        return [
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                open_time=start + timedelta(minutes=minutes * index),
                close_time=start + timedelta(minutes=minutes * (index + 1)),
                open=100.0 + index,
                high=101.0 + index,
                low=99.0 + index,
                close=100.5 + index,
                volume=1_000.0 + index,
                is_closed=True,
                source="binance",
            )
            for index in range(limit)
        ]

    def fetch_ticker(self, symbol: str) -> object:
        raise NotImplementedError


def _plan(
    tmp_path: Path,
    *,
    symbols: tuple[str, ...] = ("ETH/USDT", "BTC/USDT"),
    timeframes: tuple[str, ...] = ("4h", "1m", "15m", "3m", "5m", "1h", "30m"),
) -> FuturesDatasetCampaignPlan:
    return plan_futures_dataset_campaign(
        campaign_id="n46-matrix",
        symbols=symbols,
        timeframes=timeframes,
        provider="binance",
        candle_count=9,
        output_directory=tmp_path / "datasets",
    )


def test_timeframes_are_normalized_into_canonical_duration_order() -> None:
    assert normalize_campaign_timeframes(("4h", "1m", "15m", "3m", "5m", "1h", "30m")) == (
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1h",
        "4h",
    )


def test_duplicate_timeframe_is_rejected_after_normalization() -> None:
    with pytest.raises(ValueError, match="duplicates after normalization"):
        normalize_campaign_timeframes(("1m", " 1m "))


@pytest.mark.parametrize("timeframe", ("", "0m", "abc", "2m"))
def test_malformed_or_unsupported_timeframe_is_rejected(timeframe: str) -> None:
    with pytest.raises(ValueError):
        normalize_campaign_timeframes((timeframe,))


def test_matrix_order_count_and_ids_are_stable_across_input_order(tmp_path: Path) -> None:
    first = _plan(tmp_path)
    second = _plan(
        tmp_path,
        symbols=("BTC/USDT", "ETH/USDT"),
        timeframes=("30m", "5m", "1h", "3m", "4h", "15m", "1m"),
    )

    assert first == second
    assert len(first.jobs) == 14
    assert tuple(job.acquisition_order for job in first.jobs) == tuple(range(1, 15))
    assert tuple((job.symbol, job.timeframe) for job in first.jobs) == first.expected_matrix()
    assert tuple(job.dataset_ids() for job in first.jobs) == tuple(
        job.dataset_ids() for job in second.jobs
    )


def test_schema_version_2_round_trip(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    path = tmp_path / "plan.json"

    write_futures_dataset_campaign_plan(path, plan)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == FUTURES_DATASET_CAMPAIGN_SCHEMA_VERSION
    assert payload["timeframes"] == ["1m", "3m", "5m", "15m", "30m", "1h", "4h"]
    assert "timeframe" not in payload
    assert load_futures_dataset_campaign_plan(path) == plan


def test_schema_version_1_loads_without_mutating_file(tmp_path: Path) -> None:
    plan = plan_futures_dataset_campaign(
        campaign_id="legacy",
        symbols=("BTC/USDT",),
        timeframe="5m",
        provider="binance",
        candle_count=9,
        output_directory=tmp_path / "datasets",
    )
    payload = plan.to_payload()
    payload["schema_version"] = 1
    payload["timeframe"] = "5m"
    del payload["timeframes"]
    original = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path = tmp_path / "legacy.json"
    path.write_text(original, encoding="utf-8")

    loaded = load_futures_dataset_campaign_plan(path)

    assert loaded.schema_version == 1
    assert loaded.timeframes == ("5m",)
    assert path.read_text(encoding="utf-8") == original


def test_missing_and_duplicate_matrix_pairs_are_rejected(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    with pytest.raises(ValueError, match="ordered by normalized symbol"):
        replace(plan, jobs=plan.jobs[:-1])
    duplicate = replace(plan.jobs[-1], acquisition_order=len(plan.jobs) + 1)
    with pytest.raises(ValueError, match="duplicate symbol/timeframe"):
        replace(plan, jobs=(*plan.jobs, duplicate))


def test_multi_timeframe_execution_uses_exact_frozen_order(tmp_path: Path) -> None:
    plan = _plan(
        tmp_path,
        symbols=("ETH/USDT", "BTC/USDT"),
        timeframes=("5m", "1m", "4h"),
    )
    provider = FakeProvider()
    result = execute_futures_dataset_campaign(
        plan=plan,
        provider=provider,
        configured_provider="binance",
        extracted_at=datetime(2026, 1, 2, tzinfo=UTC),
        execution_manifest_path=tmp_path / "execution.json",
    )

    assert provider.calls == [
        ("BTC/USDT", "1m", 9),
        ("BTC/USDT", "5m", 9),
        ("BTC/USDT", "4h", 9),
        ("ETH/USDT", "1m", 9),
        ("ETH/USDT", "5m", 9),
        ("ETH/USDT", "4h", 9),
    ]
    verify_futures_dataset_campaign_matrix(plan, result.jobs)
    verify_futures_dataset_campaign_execution(plan=plan, result=result)


def test_cli_repeated_timeframes_create_complete_matrix(tmp_path: Path) -> None:
    symbols = tmp_path / "symbols.yaml"
    symbols.write_text("symbols:\n  - ETH/USDT\n  - BTC/USDT\n", encoding="utf-8")
    manifest = tmp_path / "plan.json"
    result = runner.invoke(
        app,
        [
            "dataset",
            "campaign-plan",
            "--campaign-id",
            "n46-cli",
            "--symbols-file",
            str(symbols),
            "--timeframe",
            "4h",
            "--timeframe",
            "1m",
            "--timeframe",
            "5m",
            "--candles",
            "9",
            "--output-dir",
            str(tmp_path / "datasets"),
            "--manifest-output",
            str(manifest),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "symbols=2" in result.stdout
    assert "timeframes=1m,5m,4h" in result.stdout
    assert "jobs=6" in result.stdout
    assert load_futures_dataset_campaign_plan(manifest).timeframes == ("1m", "5m", "4h")
