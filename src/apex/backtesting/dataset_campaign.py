"""Deterministic planning for historical futures dataset campaigns."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apex.backtesting.dataset_acquisition import MAXIMUM_DATASET_CANDLES
from apex.backtesting.dataset_split import FuturesDatasetSplitRatios

FUTURES_DATASET_CAMPAIGN_SCHEMA_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class FuturesDatasetCampaignJob:
    """One planned parent acquisition and its deterministic split artifacts."""

    acquisition_order: int
    symbol: str
    timeframe: str
    provider: str
    candle_count: int
    parent_dataset_id: str
    train_dataset_id: str
    validation_dataset_id: str
    final_test_dataset_id: str
    parent_dataset_path: str
    train_dataset_path: str
    validation_dataset_path: str
    final_test_dataset_path: str
    split_manifest_path: str

    def __post_init__(self) -> None:
        if self.acquisition_order < 1:
            raise ValueError("campaign acquisition order must be positive")

        for name in (
            "symbol",
            "timeframe",
            "provider",
            "parent_dataset_id",
            "train_dataset_id",
            "validation_dataset_id",
            "final_test_dataset_id",
            "parent_dataset_path",
            "train_dataset_path",
            "validation_dataset_path",
            "final_test_dataset_path",
            "split_manifest_path",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"campaign job {name.replace('_', ' ')} cannot be empty")

        if not 1 <= self.candle_count <= MAXIMUM_DATASET_CANDLES:
            raise ValueError(
                f"campaign job candle count must be between one and {MAXIMUM_DATASET_CANDLES}"
            )

        expected_child_ids = (
            f"{self.parent_dataset_id}-train",
            f"{self.parent_dataset_id}-validation",
            f"{self.parent_dataset_id}-final-test",
        )
        actual_child_ids = (
            self.train_dataset_id,
            self.validation_dataset_id,
            self.final_test_dataset_id,
        )
        if actual_child_ids != expected_child_ids:
            raise ValueError("campaign child dataset IDs must be derived from the parent ID")

        if len(set(self.artifact_paths())) != len(self.artifact_paths()):
            raise ValueError("campaign job artifact paths must be unique")

    def artifact_paths(self) -> tuple[str, ...]:
        """Return every file path owned by this job."""

        return (
            self.parent_dataset_path,
            self.train_dataset_path,
            self.validation_dataset_path,
            self.final_test_dataset_path,
            self.split_manifest_path,
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "acquisition_order": self.acquisition_order,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "provider": self.provider,
            "candle_count": self.candle_count,
            "datasets": {
                "parent": {
                    "dataset_id": self.parent_dataset_id,
                    "path": self.parent_dataset_path,
                },
                "train": {
                    "dataset_id": self.train_dataset_id,
                    "path": self.train_dataset_path,
                },
                "validation": {
                    "dataset_id": self.validation_dataset_id,
                    "path": self.validation_dataset_path,
                },
                "final_test": {
                    "dataset_id": self.final_test_dataset_id,
                    "path": self.final_test_dataset_path,
                },
            },
            "split_manifest_path": self.split_manifest_path,
        }


@dataclass(frozen=True, slots=True)
class FuturesDatasetCampaignPlan:
    """Immutable acquisition plan for a reproducible historical campaign."""

    campaign_id: str
    timeframe: str
    provider: str
    candle_count: int
    output_directory: str
    split_ratios: FuturesDatasetSplitRatios
    jobs: tuple[FuturesDatasetCampaignJob, ...]
    schema_version: int = FUTURES_DATASET_CAMPAIGN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("campaign_id", "timeframe", "provider", "output_directory"):
            if not getattr(self, name).strip():
                raise ValueError(f"campaign {name.replace('_', ' ')} cannot be empty")

        if not 1 <= self.candle_count <= MAXIMUM_DATASET_CANDLES:
            raise ValueError(
                f"campaign candle count must be between one and {MAXIMUM_DATASET_CANDLES}"
            )
        if not self.jobs:
            raise ValueError("campaign plan requires at least one job")
        if self.schema_version != FUTURES_DATASET_CAMPAIGN_SCHEMA_VERSION:
            raise ValueError("unsupported futures dataset campaign schema version")

        expected_orders = tuple(range(1, len(self.jobs) + 1))
        actual_orders = tuple(job.acquisition_order for job in self.jobs)
        if actual_orders != expected_orders:
            raise ValueError("campaign acquisition order must be contiguous and deterministic")

        symbols = tuple(job.symbol for job in self.jobs)
        if symbols != tuple(sorted(symbols)):
            raise ValueError("campaign jobs must be ordered by normalized symbol")
        if len(set(symbols)) != len(symbols):
            raise ValueError("campaign jobs cannot contain duplicate symbols")

        parent_ids = tuple(job.parent_dataset_id for job in self.jobs)
        if len(set(parent_ids)) != len(parent_ids):
            raise ValueError("campaign parent dataset IDs must be unique")

        all_paths = tuple(path for job in self.jobs for path in job.artifact_paths())
        if len(set(all_paths)) != len(all_paths):
            raise ValueError("campaign jobs contain conflicting output paths")

        for job in self.jobs:
            if job.timeframe != self.timeframe:
                raise ValueError("campaign job timeframe does not match campaign")
            if job.provider != self.provider:
                raise ValueError("campaign job provider does not match campaign")
            if job.candle_count != self.candle_count:
                raise ValueError("campaign job candle count does not match campaign")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "campaign_id": self.campaign_id,
            "provider": self.provider,
            "timeframe": self.timeframe,
            "candle_count": self.candle_count,
            "output_directory": self.output_directory,
            "split_ratios": self.split_ratios.to_payload(),
            "jobs": [job.to_payload() for job in self.jobs],
        }


def plan_futures_dataset_campaign(
    *,
    campaign_id: str,
    symbols: tuple[str, ...],
    timeframe: str,
    provider: str,
    candle_count: int,
    output_directory: Path,
    split_ratios: FuturesDatasetSplitRatios | None = None,
    reserved_output_paths: tuple[Path, ...] = (),
) -> FuturesDatasetCampaignPlan:
    """Build a deterministic campaign without acquiring market data."""

    normalized_campaign_id = _identifier_part(campaign_id)
    normalized_timeframe = timeframe.strip().lower()
    normalized_provider = provider.strip().lower()

    if not normalized_timeframe:
        raise ValueError("campaign timeframe cannot be empty")
    if not normalized_provider:
        raise ValueError("campaign provider cannot be empty")
    if not 1 <= candle_count <= MAXIMUM_DATASET_CANDLES:
        raise ValueError(f"campaign candle count must be between one and {MAXIMUM_DATASET_CANDLES}")

    normalized_symbols = tuple(_normalize_symbol(symbol) for symbol in symbols)
    if not normalized_symbols:
        raise ValueError("campaign requires at least one symbol")
    if len(set(normalized_symbols)) != len(normalized_symbols):
        raise ValueError("campaign symbols contain duplicates after normalization")

    ordered_symbols = tuple(sorted(normalized_symbols))
    normalized_output_directory = _normalize_path(output_directory)
    ratios = split_ratios or FuturesDatasetSplitRatios()

    jobs = tuple(
        _build_job(
            acquisition_order=index,
            campaign_id=normalized_campaign_id,
            symbol=symbol,
            timeframe=normalized_timeframe,
            provider=normalized_provider,
            candle_count=candle_count,
            output_directory=normalized_output_directory,
        )
        for index, symbol in enumerate(ordered_symbols, start=1)
    )

    planned_paths = {_normalize_path(Path(path)) for job in jobs for path in job.artifact_paths()}
    reserved_paths = {_normalize_path(path) for path in reserved_output_paths}
    conflicts = tuple(sorted(planned_paths & reserved_paths))
    if conflicts:
        raise ValueError(f"campaign output path conflicts with a reserved path: {conflicts[0]}")

    return FuturesDatasetCampaignPlan(
        campaign_id=normalized_campaign_id,
        timeframe=normalized_timeframe,
        provider=normalized_provider,
        candle_count=candle_count,
        output_directory=normalized_output_directory,
        split_ratios=ratios,
        jobs=jobs,
    )


def write_futures_dataset_campaign_plan(
    path: Path,
    plan: FuturesDatasetCampaignPlan,
) -> None:
    """Persist a campaign plan with atomic replacement."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(plan.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_futures_dataset_campaign_plan(path: Path) -> FuturesDatasetCampaignPlan:
    """Load and completely validate a persisted campaign plan."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("futures dataset campaign payload must be an object")

    raw_ratios = payload.get("split_ratios")
    raw_jobs = payload.get("jobs")
    if not isinstance(raw_ratios, dict):
        raise ValueError("campaign split ratios must be an object")
    if not isinstance(raw_jobs, list):
        raise ValueError("campaign jobs must be a list")

    ratios = FuturesDatasetSplitRatios(
        train=float(raw_ratios["train"]),
        validation=float(raw_ratios["validation"]),
        final_test=float(raw_ratios["final_test"]),
    )

    jobs: list[FuturesDatasetCampaignJob] = []
    for raw_job in raw_jobs:
        if not isinstance(raw_job, dict):
            raise ValueError("campaign job must be an object")

        raw_datasets = raw_job.get("datasets")
        if not isinstance(raw_datasets, dict):
            raise ValueError("campaign job datasets must be an object")

        parent = _dataset_payload(raw_datasets, "parent")
        train = _dataset_payload(raw_datasets, "train")
        validation = _dataset_payload(raw_datasets, "validation")
        final_test = _dataset_payload(raw_datasets, "final_test")

        jobs.append(
            FuturesDatasetCampaignJob(
                acquisition_order=int(raw_job["acquisition_order"]),
                symbol=str(raw_job["symbol"]),
                timeframe=str(raw_job["timeframe"]),
                provider=str(raw_job["provider"]),
                candle_count=int(raw_job["candle_count"]),
                parent_dataset_id=str(parent["dataset_id"]),
                train_dataset_id=str(train["dataset_id"]),
                validation_dataset_id=str(validation["dataset_id"]),
                final_test_dataset_id=str(final_test["dataset_id"]),
                parent_dataset_path=str(parent["path"]),
                train_dataset_path=str(train["path"]),
                validation_dataset_path=str(validation["path"]),
                final_test_dataset_path=str(final_test["path"]),
                split_manifest_path=str(raw_job["split_manifest_path"]),
            )
        )

    return FuturesDatasetCampaignPlan(
        schema_version=int(payload["schema_version"]),
        campaign_id=str(payload["campaign_id"]),
        timeframe=str(payload["timeframe"]),
        provider=str(payload["provider"]),
        candle_count=int(payload["candle_count"]),
        output_directory=str(payload["output_directory"]),
        split_ratios=ratios,
        jobs=tuple(jobs),
    )


def _build_job(
    *,
    acquisition_order: int,
    campaign_id: str,
    symbol: str,
    timeframe: str,
    provider: str,
    candle_count: int,
    output_directory: str,
) -> FuturesDatasetCampaignJob:
    dataset_id = f"{campaign_id}-{_identifier_part(symbol)}-{_identifier_part(timeframe)}"
    output_path = Path(output_directory)

    return FuturesDatasetCampaignJob(
        acquisition_order=acquisition_order,
        symbol=symbol,
        timeframe=timeframe,
        provider=provider,
        candle_count=candle_count,
        parent_dataset_id=dataset_id,
        train_dataset_id=f"{dataset_id}-train",
        validation_dataset_id=f"{dataset_id}-validation",
        final_test_dataset_id=f"{dataset_id}-final-test",
        parent_dataset_path=_normalize_path(output_path / f"{dataset_id}.json"),
        train_dataset_path=_normalize_path(output_path / f"{dataset_id}-train.json"),
        validation_dataset_path=_normalize_path(output_path / f"{dataset_id}-validation.json"),
        final_test_dataset_path=_normalize_path(output_path / f"{dataset_id}-final-test.json"),
        split_manifest_path=_normalize_path(output_path / f"{dataset_id}-splits.json"),
    )


def _dataset_payload(
    datasets: dict[object, object],
    role: str,
) -> dict[object, object]:
    value = datasets.get(role)
    if not isinstance(value, dict):
        raise ValueError(f"campaign {role} dataset must be an object")
    return value


def _normalize_symbol(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("campaign symbol cannot be empty")
    return normalized


def _identifier_part(value: str) -> str:
    normalized = "".join(character.lower() for character in value.strip() if character.isalnum())
    if not normalized:
        raise ValueError("campaign identifier component cannot be empty")
    return normalized


def _normalize_path(path: Path) -> str:
    return Path(os.path.normpath(str(path))).as_posix()
