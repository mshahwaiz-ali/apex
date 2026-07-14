"""Deterministic chronological futures-dataset split tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from apex.backtesting import (
    FuturesDatasetSplitRatios,
    allocate_split_counts,
    build_futures_dataset,
    load_and_verify_futures_dataset_split,
    load_futures_dataset_split_manifest,
    split_futures_dataset,
    verify_futures_dataset_split,
    write_futures_dataset,
    write_futures_dataset_split_manifest,
)
from apex.cli import app
from apex.domain.models import Candle

runner = CliRunner()


def test_default_split_boundaries_are_deterministic() -> None:
    parent = _dataset(10)

    first = split_futures_dataset(parent)
    second = split_futures_dataset(parent)

    assert first == second
    assert (
        first.manifest.train_candle_count,
        first.manifest.validation_candle_count,
        first.manifest.final_test_candle_count,
    ) == (5, 3, 2)
    assert first.train.candles == parent.candles[:5]
    assert first.validation.candles == parent.candles[5:8]
    assert first.final_test.candles == parent.candles[8:]


def test_odd_candle_count_is_allocated_without_loss() -> None:
    ratios = FuturesDatasetSplitRatios()

    assert allocate_split_counts(11, ratios) == (6, 3, 2)


@pytest.mark.parametrize(
    ("train", "validation", "final_test", "message"),
    [
        (0.0, 0.5, 0.5, "greater than zero"),
        (-0.1, 0.6, 0.5, "greater than zero"),
        (0.5, 0.3, 0.3, "sum to 1.0"),
        (float("inf"), 0.0, 0.0, "finite"),
    ],
)
def test_ratio_validation(
    train: float,
    validation: float,
    final_test: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        FuturesDatasetSplitRatios(
            train=train,
            validation=validation,
            final_test=final_test,
        )


def test_minimum_split_size_requires_three_candles() -> None:
    with pytest.raises(ValueError, match="at least three candles"):
        split_futures_dataset(_dataset(2))


def test_every_split_contains_at_least_one_candle() -> None:
    split_set = split_futures_dataset(
        _dataset(3),
        ratios=FuturesDatasetSplitRatios(
            train=0.98,
            validation=0.01,
            final_test=0.01,
        ),
    )

    assert len(split_set.train.candles) == 1
    assert len(split_set.validation.candles) == 1
    assert len(split_set.final_test.candles) == 1


def test_children_reconstruct_parent_without_drop_overlap_or_reordering() -> None:
    parent = _dataset(17)
    split_set = split_futures_dataset(parent)

    reconstructed = (
        split_set.train.candles + split_set.validation.candles + split_set.final_test.candles
    )

    assert reconstructed == parent.candles
    assert len(reconstructed) == len(parent.candles)
    assert len({candle.open_time for candle in reconstructed}) == len(parent.candles)
    verify_futures_dataset_split(parent=parent, split_set=split_set)


def test_child_ids_are_derived_from_parent() -> None:
    split_set = split_futures_dataset(_dataset(9))

    assert split_set.train.manifest.dataset_id == "btc-5m-parent-train"
    assert split_set.validation.manifest.dataset_id == "btc-5m-parent-validation"
    assert split_set.final_test.manifest.dataset_id == "btc-5m-parent-final-test"


def test_split_manifest_json_round_trip(tmp_path: Path) -> None:
    split_set = split_futures_dataset(_dataset(9))
    path = tmp_path / "splits.json"

    write_futures_dataset_split_manifest(path, split_set.manifest)

    assert load_futures_dataset_split_manifest(path) == split_set.manifest


def test_reload_verifies_complete_split_set(tmp_path: Path) -> None:
    parent = _dataset(13)
    split_set = split_futures_dataset(parent)
    paths = _write_split_files(tmp_path, parent, split_set)

    loaded_parent, loaded_split_set = load_and_verify_futures_dataset_split(
        parent_path=paths["parent"],
        train_path=paths["train"],
        validation_path=paths["validation"],
        final_test_path=paths["final_test"],
        manifest_path=paths["manifest"],
    )

    assert loaded_parent == parent
    assert loaded_split_set == split_set


def test_tampered_child_hash_is_rejected(tmp_path: Path) -> None:
    parent = _dataset(9)
    split_set = split_futures_dataset(parent)
    paths = _write_split_files(tmp_path, parent, split_set)

    payload = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    payload["splits"]["train"]["content_hash"] = "0" * 64
    paths["manifest"].write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="train dataset hash"):
        load_and_verify_futures_dataset_split(
            parent_path=paths["parent"],
            train_path=paths["train"],
            validation_path=paths["validation"],
            final_test_path=paths["final_test"],
            manifest_path=paths["manifest"],
        )


def test_tampered_parent_hash_is_rejected(tmp_path: Path) -> None:
    parent = _dataset(9)
    split_set = split_futures_dataset(parent)
    paths = _write_split_files(tmp_path, parent, split_set)

    payload = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    payload["parent"]["content_hash"] = "0" * 64
    paths["manifest"].write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="parent hash"):
        load_and_verify_futures_dataset_split(
            parent_path=paths["parent"],
            train_path=paths["train"],
            validation_path=paths["validation"],
            final_test_path=paths["final_test"],
            manifest_path=paths["manifest"],
        )


def test_dataset_split_command_is_registered() -> None:
    result = runner.invoke(app, ["dataset", "--help"])

    assert result.exit_code == 0
    assert "split" in result.stdout


def test_dataset_split_cli_writes_and_reloads_all_files(
    tmp_path: Path,
) -> None:
    parent = _dataset(10)
    parent_path = tmp_path / "parent.json"
    train_path = tmp_path / "train.json"
    validation_path = tmp_path / "validation.json"
    final_test_path = tmp_path / "final-test.json"
    manifest_path = tmp_path / "splits.json"
    write_futures_dataset(parent_path, parent)

    result = runner.invoke(
        app,
        [
            "dataset",
            "split",
            "--input",
            str(parent_path),
            "--train-output",
            str(train_path),
            "--validation-output",
            str(validation_path),
            "--test-output",
            str(final_test_path),
            "--manifest-output",
            str(manifest_path),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "DATASET_SPLIT" in result.stdout
    assert "train_candles=5" in result.stdout
    assert "validation_candles=3" in result.stdout
    assert "final_test_candles=2" in result.stdout

    _, split_set = load_and_verify_futures_dataset_split(
        parent_path=parent_path,
        train_path=train_path,
        validation_path=validation_path,
        final_test_path=final_test_path,
        manifest_path=manifest_path,
    )
    assert (
        split_set.train.candles + split_set.validation.candles + split_set.final_test.candles
    ) == parent.candles


def _write_split_files(
    tmp_path: Path,
    parent: object,
    split_set: object,
) -> dict[str, Path]:
    from apex.backtesting import FuturesCandleDataset, FuturesDatasetSplitSet

    assert isinstance(parent, FuturesCandleDataset)
    assert isinstance(split_set, FuturesDatasetSplitSet)

    paths = {
        "parent": tmp_path / "parent.json",
        "train": tmp_path / "train.json",
        "validation": tmp_path / "validation.json",
        "final_test": tmp_path / "final-test.json",
        "manifest": tmp_path / "splits.json",
    }

    write_futures_dataset(paths["parent"], parent)
    write_futures_dataset(paths["train"], split_set.train)
    write_futures_dataset(paths["validation"], split_set.validation)
    write_futures_dataset(paths["final_test"], split_set.final_test)
    write_futures_dataset_split_manifest(
        paths["manifest"],
        split_set.manifest,
    )
    return paths


def _dataset(candle_count: int):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = tuple(
        Candle(
            symbol="BTCUSDT",
            timeframe="5m",
            open_time=start + timedelta(minutes=index * 5),
            close_time=start + timedelta(minutes=(index + 1) * 5),
            open=100.0 + index,
            high=102.0 + index,
            low=99.0 + index,
            close=101.0 + index,
            volume=1_000.0 + index,
            is_closed=True,
            source="binance",
        )
        for index in range(candle_count)
    )
    return build_futures_dataset(
        dataset_id="btc-5m-parent",
        candles=candles,
        extracted_at=datetime(2026, 7, 15, tzinfo=UTC),
    )
