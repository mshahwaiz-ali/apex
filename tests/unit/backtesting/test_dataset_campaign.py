"""Deterministic historical dataset campaign planning tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from apex.backtesting import (
    FuturesDatasetSplitRatios,
    load_futures_dataset_campaign_plan,
    plan_futures_dataset_campaign,
    write_futures_dataset_campaign_plan,
)
from apex.cli import app

runner = CliRunner()


def test_job_order_is_stable_regardless_of_input_order(tmp_path: Path) -> None:
    first = _plan(
        tmp_path,
        symbols=("SOL/USDT", "BTC/USDT", "ETH/USDT"),
    )
    second = _plan(
        tmp_path,
        symbols=("ETH/USDT", "SOL/USDT", "BTC/USDT"),
    )

    assert first == second
    assert tuple(job.symbol for job in first.jobs) == (
        "BTC/USDT",
        "ETH/USDT",
        "SOL/USDT",
    )
    assert tuple(job.acquisition_order for job in first.jobs) == (1, 2, 3)


def test_dataset_ids_and_paths_are_stable(tmp_path: Path) -> None:
    plan = _plan(tmp_path, symbols=("BTC/USDT",))
    job = plan.jobs[0]

    assert job.parent_dataset_id == "baseline-btcusdt-5m"
    assert job.train_dataset_id == "baseline-btcusdt-5m-train"
    assert job.validation_dataset_id == "baseline-btcusdt-5m-validation"
    assert job.final_test_dataset_id == "baseline-btcusdt-5m-final-test"
    assert job.parent_dataset_path.endswith("/baseline-btcusdt-5m.json")
    assert job.train_dataset_path.endswith("/baseline-btcusdt-5m-train.json")
    assert job.validation_dataset_path.endswith("/baseline-btcusdt-5m-validation.json")
    assert job.final_test_dataset_path.endswith("/baseline-btcusdt-5m-final-test.json")
    assert job.split_manifest_path.endswith("/baseline-btcusdt-5m-splits.json")


def test_duplicate_symbols_are_rejected_after_normalization(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="duplicates after normalization"):
        _plan(
            tmp_path,
            symbols=("BTC/USDT", " btc/usdt "),
        )


def test_invalid_ratios_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"sum to 1\.0"):
        _plan(
            tmp_path,
            ratios=FuturesDatasetSplitRatios(
                train=0.50,
                validation=0.30,
                final_test=0.30,
            ),
        )


def test_reserved_manifest_path_conflict_is_rejected(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "datasets"
    conflicting_manifest = output_dir / "baseline-btcusdt-5m.json"

    with pytest.raises(ValueError, match="reserved path"):
        plan_futures_dataset_campaign(
            campaign_id="baseline",
            symbols=("BTC/USDT",),
            timeframe="5m",
            provider="binance",
            candle_count=999,
            output_directory=output_dir,
            reserved_output_paths=(conflicting_manifest,),
        )


def test_json_round_trip(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    path = tmp_path / "campaign.json"

    write_futures_dataset_campaign_plan(path, plan)

    assert load_futures_dataset_campaign_plan(path) == plan


def test_tampered_conflicting_paths_are_rejected(tmp_path: Path) -> None:
    plan = _plan(tmp_path, symbols=("BTC/USDT", "ETH/USDT"))
    path = tmp_path / "campaign.json"
    write_futures_dataset_campaign_plan(path, plan)

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["jobs"][1]["datasets"]["parent"]["path"] = payload["jobs"][0]["datasets"]["parent"][
        "path"
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="conflicting output paths"):
        load_futures_dataset_campaign_plan(path)


def test_campaign_plan_command_is_registered() -> None:
    result = runner.invoke(app, ["dataset", "--help"])

    assert result.exit_code == 0
    assert "campaign-plan" in result.stdout


def test_campaign_plan_cli_writes_and_reloads_manifest(
    tmp_path: Path,
) -> None:
    symbols_path = tmp_path / "symbols.yaml"
    symbols_path.write_text(
        "symbols:\n  - ETH/USDT\n  - BTC/USDT\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "campaign.json"
    output_dir = tmp_path / "datasets"

    result = runner.invoke(
        app,
        [
            "dataset",
            "campaign-plan",
            "--campaign-id",
            "initial-baseline",
            "--symbols-file",
            str(symbols_path),
            "--timeframe",
            "5m",
            "--candles",
            "999",
            "--provider",
            "binance",
            "--output-dir",
            str(output_dir),
            "--manifest-output",
            str(manifest_path),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "DATASET_CAMPAIGN_PLANNED" in result.stdout
    assert "campaign_id=initialbaseline" in result.stdout
    assert "jobs=2" in result.stdout

    loaded = load_futures_dataset_campaign_plan(manifest_path)
    assert tuple(job.symbol for job in loaded.jobs) == (
        "BTC/USDT",
        "ETH/USDT",
    )
    assert loaded.candle_count == 999
    assert loaded.split_ratios == FuturesDatasetSplitRatios()


def _plan(
    tmp_path: Path,
    *,
    symbols: tuple[str, ...] = ("ETH/USDT", "BTC/USDT"),
    ratios: FuturesDatasetSplitRatios | None = None,
):
    return plan_futures_dataset_campaign(
        campaign_id="baseline",
        symbols=symbols,
        timeframe="5m",
        provider="binance",
        candle_count=999,
        output_directory=tmp_path / "datasets",
        split_ratios=ratios,
    )
