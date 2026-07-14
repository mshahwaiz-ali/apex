"""CLI tests for deterministic dataset campaign execution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from apex.backtesting.dataset_campaign import (
    plan_futures_dataset_campaign,
    write_futures_dataset_campaign_plan,
)
from apex.backtesting.dataset_campaign_execution import (
    load_futures_dataset_campaign_execution_result,
)
from apex.cli import app
from apex.domain.models import Candle


class FakeProvider:
    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> list[Candle]:
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
                volume=1_000.0,
                is_closed=True,
                source="binance",
            )
            for index in range(limit)
        ]

    def fetch_ticker(self, symbol: str) -> object:
        raise NotImplementedError


class FakeServices:
    def __init__(self) -> None:
        self.candles = FakeProvider()

    def __enter__(self) -> FakeServices:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _plan_file(tmp_path: Path, *, provider: str = "binance") -> Path:
    plan = plan_futures_dataset_campaign(
        campaign_id="cli-n45",
        symbols=("BTC/USDT",),
        timeframe="5m",
        provider=provider,
        candle_count=9,
        output_directory=tmp_path / "datasets",
    )
    path = tmp_path / "plan.json"
    write_futures_dataset_campaign_plan(path, plan)
    return path


def test_campaign_execute_is_registered() -> None:
    result = CliRunner().invoke(app, ["dataset", "--help"])

    assert result.exit_code == 0
    assert "campaign-execute" in result.stdout


def test_campaign_execute_cli_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_file = _plan_file(tmp_path)
    manifest = tmp_path / "execution.json"

    monkeypatch.setattr(
        "apex.cli.create_market_data_services",
        lambda settings, provider_name="binance": FakeServices(),
    )

    result = CliRunner().invoke(
        app,
        [
            "dataset",
            "campaign-execute",
            "--plan",
            str(plan_file),
            "--execution-manifest-output",
            str(manifest),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "DATASET_CAMPAIGN_EXECUTED" in result.stdout
    loaded = load_futures_dataset_campaign_execution_result(manifest)
    assert loaded.completed_jobs == 1
    assert loaded.failed_jobs == 0


def test_campaign_execute_cli_rejects_provider_mismatch(tmp_path: Path) -> None:
    plan_file = _plan_file(tmp_path, provider="other")
    manifest = tmp_path / "execution.json"

    result = CliRunner().invoke(
        app,
        [
            "dataset",
            "campaign-execute",
            "--plan",
            str(plan_file),
            "--execution-manifest-output",
            str(manifest),
        ],
    )

    assert result.exit_code == 2
    assert "does not match configured provider" in result.output
    assert not manifest.exists()


def test_campaign_execute_cli_rejects_existing_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_file = _plan_file(tmp_path)
    manifest = tmp_path / "execution.json"
    manifest.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(
        "apex.cli.create_market_data_services",
        lambda settings, provider_name="binance": FakeServices(),
    )

    result = CliRunner().invoke(
        app,
        [
            "dataset",
            "campaign-execute",
            "--plan",
            str(plan_file),
            "--execution-manifest-output",
            str(manifest),
        ],
    )

    assert result.exit_code == 2
    assert "refuses to overwrite" in result.output
