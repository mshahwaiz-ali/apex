"""Deterministic planning for historical futures dataset campaigns."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apex.backtesting.dataset_acquisition import MAXIMUM_DATASET_CANDLES
from apex.backtesting.dataset_split import FuturesDatasetSplitRatios

FUTURES_DATASET_CAMPAIGN_SCHEMA_VERSION: Final = 2
LEGACY_FUTURES_DATASET_CAMPAIGN_SCHEMA_VERSION: Final = 1
CANONICAL_CAMPAIGN_TIMEFRAMES: Final[tuple[str, ...]] = (
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "4h",
)
_TIMEFRAME_PATTERN: Final = re.compile(r"^[1-9][0-9]*[mhdwM]$")
_TIMEFRAME_ORDER: Final = {
    timeframe: index for index, timeframe in enumerate(CANONICAL_CAMPAIGN_TIMEFRAMES)
}


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
        if self.timeframe != normalize_campaign_timeframe(self.timeframe):
            raise ValueError("campaign job timeframe must be normalized")
        if not 1 <= self.candle_count <= MAXIMUM_DATASET_CANDLES:
            raise ValueError(
                f"campaign job candle count must be between one and {MAXIMUM_DATASET_CANDLES}"
            )
        if (
            self.train_dataset_id,
            self.validation_dataset_id,
            self.final_test_dataset_id,
        ) != (
            f"{self.parent_dataset_id}-train",
            f"{self.parent_dataset_id}-validation",
            f"{self.parent_dataset_id}-final-test",
        ):
            raise ValueError("campaign child dataset IDs must be derived from the parent ID")
        if len(set(self.dataset_ids())) != len(self.dataset_ids()):
            raise ValueError("campaign job dataset IDs must be unique")
        if len(set(self.artifact_paths())) != len(self.artifact_paths()):
            raise ValueError("campaign job artifact paths must be unique")

    def dataset_ids(self) -> tuple[str, ...]:
        return (
            self.parent_dataset_id,
            self.train_dataset_id,
            self.validation_dataset_id,
            self.final_test_dataset_id,
        )

    def artifact_paths(self) -> tuple[str, ...]:
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
    timeframes: tuple[str, ...]
    provider: str
    candle_count: int
    output_directory: str
    split_ratios: FuturesDatasetSplitRatios
    jobs: tuple[FuturesDatasetCampaignJob, ...]
    schema_version: int = FUTURES_DATASET_CAMPAIGN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("campaign_id", "provider", "output_directory"):
            if not getattr(self, name).strip():
                raise ValueError(f"campaign {name.replace('_', ' ')} cannot be empty")
        if self.timeframes != normalize_campaign_timeframes(self.timeframes):
            raise ValueError("campaign timeframes must be normalized in canonical order")
        if not 1 <= self.candle_count <= MAXIMUM_DATASET_CANDLES:
            raise ValueError(
                f"campaign candle count must be between one and {MAXIMUM_DATASET_CANDLES}"
            )
        if not self.jobs:
            raise ValueError("campaign plan requires at least one job")
        if self.schema_version not in (
            LEGACY_FUTURES_DATASET_CAMPAIGN_SCHEMA_VERSION,
            FUTURES_DATASET_CAMPAIGN_SCHEMA_VERSION,
        ):
            raise ValueError("unsupported futures dataset campaign schema version")
        if tuple(job.acquisition_order for job in self.jobs) != tuple(
            range(1, len(self.jobs) + 1)
        ):
            raise ValueError("campaign acquisition order must be contiguous and deterministic")
        pairs = tuple((job.symbol, job.timeframe) for job in self.jobs)
        if len(set(pairs)) != len(pairs):
            raise ValueError("campaign jobs cannot contain duplicate symbol/timeframe pairs")
        if pairs != self.expected_matrix():
            raise ValueError(
                "campaign jobs must be ordered by normalized symbol and canonical timeframe"
            )
        all_ids = tuple(dataset_id for job in self.jobs for dataset_id in job.dataset_ids())
        if len(set(all_ids)) != len(all_ids):
            raise ValueError("campaign jobs contain conflicting dataset IDs")
        all_paths = tuple(path for job in self.jobs for path in job.artifact_paths())
        if len(set(all_paths)) != len(all_paths):
            raise ValueError("campaign jobs contain conflicting output paths")
        for job in self.jobs:
            if job.timeframe not in self.timeframes:
                raise ValueError("campaign job timeframe is not in the campaign timeframe set")
            if job.provider != self.provider:
                raise ValueError("campaign job provider does not match campaign")
            if job.candle_count != self.candle_count:
                raise ValueError("campaign job candle count does not match campaign")

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(sorted({job.symbol for job in self.jobs}))

    def expected_matrix(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (symbol, timeframe)
            for symbol in self.symbols
            for timeframe in self.timeframes
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": FUTURES_DATASET_CAMPAIGN_SCHEMA_VERSION,
            "campaign_id": self.campaign_id,
            "provider": self.provider,
            "timeframes": list(self.timeframes),
            "candle_count": self.candle_count,
            "output_directory": self.output_directory,
            "split_ratios": self.split_ratios.to_payload(),
            "jobs": [job.to_payload() for job in self.jobs],
        }


def normalize_campaign_timeframe(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("campaign timeframe cannot be empty")
    if not _TIMEFRAME_PATTERN.fullmatch(normalized):
        raise ValueError(f"malformed campaign timeframe: {value!r}")
    if normalized not in _TIMEFRAME_ORDER:
        raise ValueError(f"unsupported campaign timeframe: {normalized}")
    return normalized


def normalize_campaign_timeframes(values: tuple[str, ...]) -> tuple[str, ...]:
    if not values:
        raise ValueError("campaign requires at least one timeframe")
    normalized = tuple(normalize_campaign_timeframe(value) for value in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError("campaign timeframes contain duplicates after normalization")
    return tuple(sorted(normalized, key=_TIMEFRAME_ORDER.__getitem__))


def verify_futures_dataset_campaign_matrix(
    plan: FuturesDatasetCampaignPlan,
    jobs: tuple[object, ...] | None = None,
) -> None:
    """Verify complete symbol × timeframe coverage for a plan or execution jobs."""

    selected = plan.jobs if jobs is None else jobs
    actual = tuple(
        (str(getattr(job, "symbol")), str(getattr(job, "timeframe"))) for job in selected
    )
    expected = plan.expected_matrix()
    if len(set(actual)) != len(actual):
        raise ValueError("campaign matrix contains duplicate symbol/timeframe pairs")
    missing = tuple(pair for pair in expected if pair not in actual)
    if missing:
        raise ValueError(
            "campaign matrix is missing symbol/timeframe pair: "
            f"{missing[0][0]} {missing[0][1]}"
        )
    extra = tuple(pair for pair in actual if pair not in expected)
    if extra:
        raise ValueError(
            "campaign matrix contains extra symbol/timeframe pair: "
            f"{extra[0][0]} {extra[0][1]}"
        )
    if actual != expected:
        raise ValueError("campaign matrix order does not match the frozen plan")


def plan_futures_dataset_campaign(
    *,
    campaign_id: str,
    symbols: tuple[str, ...],
    provider: str,
    candle_count: int,
    output_directory: Path,
    timeframes: tuple[str, ...] | None = None,
    timeframe: str | None = None,
    split_ratios: FuturesDatasetSplitRatios | None = None,
    reserved_output_paths: tuple[Path, ...] = (),
) -> FuturesDatasetCampaignPlan:
    """Build a deterministic symbol × timeframe campaign without acquiring data."""

    if timeframes is not None and timeframe is not None:
        raise ValueError("provide campaign timeframes or legacy timeframe, not both")
    raw_timeframes = timeframes if timeframes is not None else (() if timeframe is None else (timeframe,))
    normalized_timeframes = normalize_campaign_timeframes(raw_timeframes)
    normalized_campaign_id = _identifier_part(campaign_id)
    normalized_provider = provider.strip().lower()
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
    matrix = tuple(
        (symbol, job_timeframe)
        for symbol in ordered_symbols
        for job_timeframe in normalized_timeframes
    )
    jobs = tuple(
        _build_job(
            acquisition_order=index,
            campaign_id=normalized_campaign_id,
            symbol=symbol,
            timeframe=job_timeframe,
            provider=normalized_provider,
            candle_count=candle_count,
            output_directory=normalized_output_directory,
        )
        for index, (symbol, job_timeframe) in enumerate(matrix, start=1)
    )
    planned_paths = {_normalize_path(Path(path)) for job in jobs for path in job.artifact_paths()}
    reserved_paths = {_normalize_path(path) for path in reserved_output_paths}
    conflicts = tuple(sorted(planned_paths & reserved_paths))
    if conflicts:
        raise ValueError(f"campaign output path conflicts with a reserved path: {conflicts[0]}")
    return FuturesDatasetCampaignPlan(
        campaign_id=normalized_campaign_id,
        timeframes=normalized_timeframes,
        provider=normalized_provider,
        candle_count=candle_count,
        output_directory=normalized_output_directory,
        split_ratios=ratios,
        jobs=jobs,
    )


def write_futures_dataset_campaign_plan(path: Path, plan: FuturesDatasetCampaignPlan) -> None:
    """Persist a campaign plan with atomic replacement using schema version 2."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(plan.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_futures_dataset_campaign_plan(path: Path) -> FuturesDatasetCampaignPlan:
    """Load and validate schema-version-1 or schema-version-2 plans."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("futures dataset campaign payload must be an object")
    schema_version = int(payload["schema_version"])
    if schema_version == LEGACY_FUTURES_DATASET_CAMPAIGN_SCHEMA_VERSION:
        raw_timeframes = (str(payload["timeframe"]),)
    elif schema_version == FUTURES_DATASET_CAMPAIGN_SCHEMA_VERSION:
        value = payload.get("timeframes")
        if not isinstance(value, list):
            raise ValueError("campaign timeframes must be a list")
        raw_timeframes = tuple(str(item) for item in value)
    else:
        raise ValueError("unsupported futures dataset campaign schema version")
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
    jobs = tuple(_load_job(raw_job) for raw_job in raw_jobs)
    return FuturesDatasetCampaignPlan(
        schema_version=schema_version,
        campaign_id=str(payload["campaign_id"]),
        timeframes=normalize_campaign_timeframes(raw_timeframes),
        provider=str(payload["provider"]),
        candle_count=int(payload["candle_count"]),
        output_directory=str(payload["output_directory"]),
        split_ratios=ratios,
        jobs=jobs,
    )


def _load_job(raw_job: object) -> FuturesDatasetCampaignJob:
    if not isinstance(raw_job, dict):
        raise ValueError("campaign job must be an object")
    raw_datasets = raw_job.get("datasets")
    if not isinstance(raw_datasets, dict):
        raise ValueError("campaign job datasets must be an object")
    parent = _dataset_payload(raw_datasets, "parent")
    train = _dataset_payload(raw_datasets, "train")
    validation = _dataset_payload(raw_datasets, "validation")
    final_test = _dataset_payload(raw_datasets, "final_test")
    return FuturesDatasetCampaignJob(
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


def _dataset_payload(datasets: dict[object, object], role: str) -> dict[object, object]:
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
