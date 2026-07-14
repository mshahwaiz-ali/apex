"""Deterministic chronological futures-dataset splitting."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from apex.backtesting.dataset import (
    FuturesCandleDataset,
    build_futures_dataset,
    load_futures_dataset,
)

FUTURES_DATASET_SPLIT_SCHEMA_VERSION: Final = 1
DEFAULT_TRAIN_RATIO: Final = 0.60
DEFAULT_VALIDATION_RATIO: Final = 0.20
DEFAULT_FINAL_TEST_RATIO: Final = 0.20
_RATIO_TOLERANCE: Final = 1e-9


@dataclass(frozen=True, slots=True)
class FuturesDatasetSplitRatios:
    """Validated chronological train, validation, and final-test ratios."""

    train: float = DEFAULT_TRAIN_RATIO
    validation: float = DEFAULT_VALIDATION_RATIO
    final_test: float = DEFAULT_FINAL_TEST_RATIO

    def __post_init__(self) -> None:
        values = (self.train, self.validation, self.final_test)

        if any(not math.isfinite(value) for value in values):
            raise ValueError("dataset split ratios must be finite")
        if any(value <= 0.0 for value in values):
            raise ValueError("dataset split ratios must be greater than zero")
        if not math.isclose(
            sum(values),
            1.0,
            rel_tol=0.0,
            abs_tol=_RATIO_TOLERANCE,
        ):
            raise ValueError("dataset split ratios must sum to 1.0")

    def to_payload(self) -> dict[str, float]:
        return {
            "train": self.train,
            "validation": self.validation,
            "final_test": self.final_test,
        }


@dataclass(frozen=True, slots=True)
class FuturesDatasetCoverage:
    """Inclusive candle coverage boundaries for one child dataset."""

    start_time: datetime
    end_time: datetime

    def __post_init__(self) -> None:
        for name in ("start_time", "end_time"):
            value = getattr(self, name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(
                    f"dataset split coverage {name.replace('_', ' ')} must be timezone-aware"
                )

        if self.start_time > self.end_time:
            raise ValueError("dataset split coverage start cannot follow its end")

    def to_payload(self) -> dict[str, str]:
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class FuturesDatasetSplitManifest:
    """Immutable provenance and coverage for one chronological split set."""

    parent_dataset_id: str
    parent_content_hash: str
    train_dataset_id: str
    validation_dataset_id: str
    final_test_dataset_id: str
    train_content_hash: str
    validation_content_hash: str
    final_test_content_hash: str
    ratios: FuturesDatasetSplitRatios
    parent_candle_count: int
    train_candle_count: int
    validation_candle_count: int
    final_test_candle_count: int
    parent_coverage: FuturesDatasetCoverage
    train_coverage: FuturesDatasetCoverage
    validation_coverage: FuturesDatasetCoverage
    final_test_coverage: FuturesDatasetCoverage
    schema_version: int = FUTURES_DATASET_SPLIT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        identifiers = (
            self.parent_dataset_id,
            self.train_dataset_id,
            self.validation_dataset_id,
            self.final_test_dataset_id,
        )
        if any(not value.strip() for value in identifiers):
            raise ValueError("dataset split identifiers cannot be empty")

        hashes = (
            self.parent_content_hash,
            self.train_content_hash,
            self.validation_content_hash,
            self.final_test_content_hash,
        )
        if any(not _is_sha256(value) for value in hashes):
            raise ValueError("dataset split content hashes must be SHA-256 hex digests")

        counts = (
            self.parent_candle_count,
            self.train_candle_count,
            self.validation_candle_count,
            self.final_test_candle_count,
        )
        if any(value < 1 for value in counts):
            raise ValueError("every dataset split count must be positive")

        child_total = (
            self.train_candle_count + self.validation_candle_count + self.final_test_candle_count
        )
        if child_total != self.parent_candle_count:
            raise ValueError("dataset split child counts must equal the parent count")

        if self.schema_version != FUTURES_DATASET_SPLIT_SCHEMA_VERSION:
            raise ValueError("unsupported futures dataset split schema version")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "parent": {
                "dataset_id": self.parent_dataset_id,
                "content_hash": self.parent_content_hash,
                "candle_count": self.parent_candle_count,
                "coverage": self.parent_coverage.to_payload(),
            },
            "ratios": self.ratios.to_payload(),
            "splits": {
                "train": {
                    "dataset_id": self.train_dataset_id,
                    "content_hash": self.train_content_hash,
                    "candle_count": self.train_candle_count,
                    "coverage": self.train_coverage.to_payload(),
                },
                "validation": {
                    "dataset_id": self.validation_dataset_id,
                    "content_hash": self.validation_content_hash,
                    "candle_count": self.validation_candle_count,
                    "coverage": self.validation_coverage.to_payload(),
                },
                "final_test": {
                    "dataset_id": self.final_test_dataset_id,
                    "content_hash": self.final_test_content_hash,
                    "candle_count": self.final_test_candle_count,
                    "coverage": self.final_test_coverage.to_payload(),
                },
            },
        }


@dataclass(frozen=True, slots=True)
class FuturesDatasetSplitSet:
    """A parent dataset divided into three chronological child datasets."""

    manifest: FuturesDatasetSplitManifest
    train: FuturesCandleDataset
    validation: FuturesCandleDataset
    final_test: FuturesCandleDataset

    def __post_init__(self) -> None:
        _verify_child_manifest(
            role="train",
            dataset=self.train,
            expected_id=self.manifest.train_dataset_id,
            expected_hash=self.manifest.train_content_hash,
            expected_count=self.manifest.train_candle_count,
            expected_coverage=self.manifest.train_coverage,
        )
        _verify_child_manifest(
            role="validation",
            dataset=self.validation,
            expected_id=self.manifest.validation_dataset_id,
            expected_hash=self.manifest.validation_content_hash,
            expected_count=self.manifest.validation_candle_count,
            expected_coverage=self.manifest.validation_coverage,
        )
        _verify_child_manifest(
            role="final test",
            dataset=self.final_test,
            expected_id=self.manifest.final_test_dataset_id,
            expected_hash=self.manifest.final_test_content_hash,
            expected_count=self.manifest.final_test_candle_count,
            expected_coverage=self.manifest.final_test_coverage,
        )

        child_open_times = [
            candle.open_time
            for dataset in (self.train, self.validation, self.final_test)
            for candle in dataset.candles
        ]
        if len(child_open_times) != len(set(child_open_times)):
            raise ValueError("dataset splits cannot overlap or duplicate candles")

        combined = self.train.candles + self.validation.candles + self.final_test.candles
        if tuple(sorted(combined, key=lambda candle: candle.open_time)) != combined:
            raise ValueError("dataset splits must remain chronological")


def split_futures_dataset(
    parent: FuturesCandleDataset,
    *,
    ratios: FuturesDatasetSplitRatios | None = None,
) -> FuturesDatasetSplitSet:
    """Split a dataset chronologically with no randomization or data loss."""

    resolved_ratios = ratios or FuturesDatasetSplitRatios()
    train_count, validation_count, _ = allocate_split_counts(
        parent.manifest.candle_count,
        resolved_ratios,
    )

    train_end = train_count
    validation_end = train_end + validation_count

    train = build_futures_dataset(
        dataset_id=f"{parent.manifest.dataset_id}-train",
        candles=parent.candles[:train_end],
        extracted_at=parent.manifest.extracted_at,
    )
    validation = build_futures_dataset(
        dataset_id=f"{parent.manifest.dataset_id}-validation",
        candles=parent.candles[train_end:validation_end],
        extracted_at=parent.manifest.extracted_at,
    )
    final_test = build_futures_dataset(
        dataset_id=f"{parent.manifest.dataset_id}-final-test",
        candles=parent.candles[validation_end:],
        extracted_at=parent.manifest.extracted_at,
    )

    manifest = FuturesDatasetSplitManifest(
        parent_dataset_id=parent.manifest.dataset_id,
        parent_content_hash=parent.manifest.content_hash,
        train_dataset_id=train.manifest.dataset_id,
        validation_dataset_id=validation.manifest.dataset_id,
        final_test_dataset_id=final_test.manifest.dataset_id,
        train_content_hash=train.manifest.content_hash,
        validation_content_hash=validation.manifest.content_hash,
        final_test_content_hash=final_test.manifest.content_hash,
        ratios=resolved_ratios,
        parent_candle_count=parent.manifest.candle_count,
        train_candle_count=train.manifest.candle_count,
        validation_candle_count=validation.manifest.candle_count,
        final_test_candle_count=final_test.manifest.candle_count,
        parent_coverage=_coverage(parent),
        train_coverage=_coverage(train),
        validation_coverage=_coverage(validation),
        final_test_coverage=_coverage(final_test),
    )

    split_set = FuturesDatasetSplitSet(
        manifest=manifest,
        train=train,
        validation=validation,
        final_test=final_test,
    )
    verify_futures_dataset_split(parent=parent, split_set=split_set)
    return split_set


def allocate_split_counts(
    candle_count: int,
    ratios: FuturesDatasetSplitRatios,
) -> tuple[int, int, int]:
    """Allocate deterministic counts while reserving one candle per split."""

    if candle_count < 3:
        raise ValueError("futures dataset requires at least three candles for splitting")

    remaining = candle_count - 3
    ratio_values = (ratios.train, ratios.validation, ratios.final_test)
    exact_allocations = tuple(remaining * ratio for ratio in ratio_values)
    extra_counts = [math.floor(value) for value in exact_allocations]
    undistributed = remaining - sum(extra_counts)

    remainder_order = sorted(
        range(3),
        key=lambda index: (
            -(exact_allocations[index] - extra_counts[index]),
            index,
        ),
    )
    for index in remainder_order[:undistributed]:
        extra_counts[index] += 1

    counts = tuple(value + 1 for value in extra_counts)
    if sum(counts) != candle_count:
        raise ValueError("dataset split allocation did not preserve candle count")
    if any(value < 1 for value in counts):
        raise ValueError("every dataset split must contain at least one candle")

    return counts[0], counts[1], counts[2]


def verify_futures_dataset_split(
    *,
    parent: FuturesCandleDataset,
    split_set: FuturesDatasetSplitSet,
) -> None:
    """Verify parent identity and exact child reconstruction."""

    manifest = split_set.manifest

    if manifest.parent_dataset_id != parent.manifest.dataset_id:
        raise ValueError("dataset split parent ID does not match loaded source")
    if manifest.parent_content_hash != parent.manifest.content_hash:
        raise ValueError("dataset split parent hash does not match loaded source")
    if manifest.parent_candle_count != parent.manifest.candle_count:
        raise ValueError("dataset split parent count does not match loaded source")
    if manifest.parent_coverage != _coverage(parent):
        raise ValueError("dataset split parent coverage does not match loaded source")

    reconstructed = (
        split_set.train.candles + split_set.validation.candles + split_set.final_test.candles
    )
    if reconstructed != parent.candles:
        raise ValueError("dataset splits do not exactly reconstruct the parent sequence")

    if len(reconstructed) != parent.manifest.candle_count:
        raise ValueError("dataset split child total does not equal parent count")

    if split_set.train.candles[-1].open_time >= (split_set.validation.candles[0].open_time):
        raise ValueError("train and validation dataset splits overlap")
    if split_set.validation.candles[-1].open_time >= (split_set.final_test.candles[0].open_time):
        raise ValueError("validation and final-test dataset splits overlap")


def write_futures_dataset_split_manifest(
    path: Path,
    manifest: FuturesDatasetSplitManifest,
) -> None:
    """Persist one split-set manifest with atomic replacement."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            manifest.to_payload(),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_futures_dataset_split_manifest(
    path: Path,
) -> FuturesDatasetSplitManifest:
    """Load and validate one persisted split-set manifest."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("futures dataset split manifest must be an object")

    raw_parent = _require_mapping(payload, "parent")
    raw_ratios = _require_mapping(payload, "ratios")
    raw_splits = _require_mapping(payload, "splits")
    raw_train = _require_mapping(raw_splits, "train")
    raw_validation = _require_mapping(raw_splits, "validation")
    raw_final_test = _require_mapping(raw_splits, "final_test")

    return FuturesDatasetSplitManifest(
        schema_version=_as_int(payload["schema_version"], "schema_version"),
        parent_dataset_id=str(raw_parent["dataset_id"]),
        parent_content_hash=str(raw_parent["content_hash"]),
        parent_candle_count=_as_int(
            raw_parent["candle_count"],
            "parent.candle_count",
        ),
        parent_coverage=_load_coverage(raw_parent),
        ratios=FuturesDatasetSplitRatios(
            train=_as_float(raw_ratios["train"], "ratios.train"),
            validation=_as_float(
                raw_ratios["validation"],
                "ratios.validation",
            ),
            final_test=_as_float(
                raw_ratios["final_test"],
                "ratios.final_test",
            ),
        ),
        train_dataset_id=str(raw_train["dataset_id"]),
        validation_dataset_id=str(raw_validation["dataset_id"]),
        final_test_dataset_id=str(raw_final_test["dataset_id"]),
        train_content_hash=str(raw_train["content_hash"]),
        validation_content_hash=str(raw_validation["content_hash"]),
        final_test_content_hash=str(raw_final_test["content_hash"]),
        train_candle_count=_as_int(
            raw_train["candle_count"],
            "splits.train.candle_count",
        ),
        validation_candle_count=_as_int(
            raw_validation["candle_count"],
            "splits.validation.candle_count",
        ),
        final_test_candle_count=_as_int(
            raw_final_test["candle_count"],
            "splits.final_test.candle_count",
        ),
        train_coverage=_load_coverage(raw_train),
        validation_coverage=_load_coverage(raw_validation),
        final_test_coverage=_load_coverage(raw_final_test),
    )


def load_and_verify_futures_dataset_split(
    *,
    parent_path: Path,
    train_path: Path,
    validation_path: Path,
    final_test_path: Path,
    manifest_path: Path,
) -> tuple[FuturesCandleDataset, FuturesDatasetSplitSet]:
    """Reload every persisted artifact and verify the complete split set."""

    parent = load_futures_dataset(parent_path)
    split_set = FuturesDatasetSplitSet(
        manifest=load_futures_dataset_split_manifest(manifest_path),
        train=load_futures_dataset(train_path),
        validation=load_futures_dataset(validation_path),
        final_test=load_futures_dataset(final_test_path),
    )
    verify_futures_dataset_split(parent=parent, split_set=split_set)
    return parent, split_set


def _coverage(dataset: FuturesCandleDataset) -> FuturesDatasetCoverage:
    return FuturesDatasetCoverage(
        start_time=dataset.manifest.start_time,
        end_time=dataset.manifest.end_time,
    )


def _verify_child_manifest(
    *,
    role: str,
    dataset: FuturesCandleDataset,
    expected_id: str,
    expected_hash: str,
    expected_count: int,
    expected_coverage: FuturesDatasetCoverage,
) -> None:
    if dataset.manifest.dataset_id != expected_id:
        raise ValueError(f"{role} dataset ID does not match split manifest")
    if dataset.manifest.content_hash != expected_hash:
        raise ValueError(f"{role} dataset hash does not match split manifest")
    if dataset.manifest.candle_count != expected_count:
        raise ValueError(f"{role} dataset count does not match split manifest")
    if _coverage(dataset) != expected_coverage:
        raise ValueError(f"{role} dataset coverage does not match split manifest")


def _load_coverage(payload: dict[str, object]) -> FuturesDatasetCoverage:
    raw_coverage = _require_mapping(payload, "coverage")
    return FuturesDatasetCoverage(
        start_time=datetime.fromisoformat(str(raw_coverage["start_time"])),
        end_time=datetime.fromisoformat(str(raw_coverage["end_time"])),
    )


def _require_mapping(
    payload: dict[str, object],
    key: str,
) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"futures dataset split manifest {key} must be an object")
    return value


def _as_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{field} must be an integer")

    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an integer") from exc


def _as_float(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{field} must be numeric")

    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be numeric") from exc


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
