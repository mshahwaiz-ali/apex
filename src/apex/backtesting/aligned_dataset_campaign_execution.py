"""Execution and verification for aligned historical dataset campaigns."""

from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import Final

from apex.backtesting.aligned_dataset_campaign import (
    AlignedDatasetCampaignJob,
    AlignedDatasetCampaignPlan,
)
from apex.backtesting.dataset import (
    build_futures_dataset,
    load_futures_dataset,
    write_futures_dataset,
)
from apex.data.providers.base import HistoricalRangeMarketDataProvider
from apex.domain.models import Candle

ALIGNED_DATASET_CAMPAIGN_EXECUTION_SCHEMA_VERSION: Final = 1
_TIMEFRAME_SECONDS: Final[dict[str, int]] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
}


@dataclass(frozen=True, slots=True)
class AlignedDatasetCampaignJobResult:
    """Verified result for one aligned acquisition job."""

    acquisition_order: int
    symbol: str
    timeframe: str
    dataset_id: str
    dataset_path: str
    content_hash: str
    candle_count: int
    warmup_candle_count: int
    first_open_time: datetime
    last_close_time: datetime

    def __post_init__(self) -> None:
        if self.acquisition_order < 1 or self.candle_count < 1 or self.warmup_candle_count < 1:
            raise ValueError("aligned execution counts must be positive")
        for value in (self.symbol, self.timeframe, self.dataset_id, self.dataset_path):
            if not value.strip():
                raise ValueError("aligned execution job fields cannot be empty")
        if not _is_sha256(self.content_hash):
            raise ValueError("aligned execution dataset hash must be SHA-256")
        _require_aware(self.first_open_time, "first open time")
        _require_aware(self.last_close_time, "last close time")

    def to_payload(self) -> dict[str, object]:
        return {
            "acquisition_order": self.acquisition_order,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "dataset_id": self.dataset_id,
            "dataset_path": self.dataset_path,
            "content_hash": self.content_hash,
            "candle_count": self.candle_count,
            "warmup_candle_count": self.warmup_candle_count,
            "first_open_time": self.first_open_time.isoformat(),
            "last_close_time": self.last_close_time.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class AlignedDatasetCampaignExecutionResult:
    """Completed aligned campaign audit manifest."""

    campaign_id: str
    provider: str
    plan_path: str
    warmup_start: datetime
    analysis_start: datetime
    train_end: datetime
    validation_end: datetime
    analysis_end: datetime
    jobs: tuple[AlignedDatasetCampaignJobResult, ...]
    schema_version: int = ALIGNED_DATASET_CAMPAIGN_EXECUTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != ALIGNED_DATASET_CAMPAIGN_EXECUTION_SCHEMA_VERSION:
            raise ValueError("unsupported aligned execution schema version")
        if not self.campaign_id.strip() or not self.provider.strip() or not self.plan_path.strip():
            raise ValueError("aligned execution fields cannot be empty")
        for name in (
            "warmup_start",
            "analysis_start",
            "train_end",
            "validation_end",
            "analysis_end",
        ):
            _require_aware(getattr(self, name), name)
        if (
            not self.warmup_start
            < self.analysis_start
            < self.train_end
            < self.validation_end
            < self.analysis_end
        ):
            raise ValueError("aligned execution boundaries must be strictly increasing")
        if not self.jobs:
            raise ValueError("aligned execution requires jobs")
        if tuple(job.acquisition_order for job in self.jobs) != tuple(range(1, len(self.jobs) + 1)):
            raise ValueError("aligned execution jobs must remain in acquisition order")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "campaign_id": self.campaign_id,
            "provider": self.provider,
            "plan_path": self.plan_path,
            "warmup_start": self.warmup_start.isoformat(),
            "boundaries": {
                "analysis_start": self.analysis_start.isoformat(),
                "train_end": self.train_end.isoformat(),
                "validation_end": self.validation_end.isoformat(),
                "analysis_end": self.analysis_end.isoformat(),
            },
            "planned_jobs": len(self.jobs),
            "completed_jobs": len(self.jobs),
            "failed_jobs": 0,
            "status": "completed",
            "jobs": [job.to_payload() for job in self.jobs],
        }


def execute_aligned_dataset_campaign(
    *,
    plan: AlignedDatasetCampaignPlan,
    provider: HistoricalRangeMarketDataProvider,
    plan_path: Path,
    execution_manifest_path: Path,
    extracted_at: datetime,
) -> AlignedDatasetCampaignExecutionResult:
    """Acquire and verify every frozen aligned campaign job."""

    _require_aware(extracted_at, "extracted at")
    if provider.name.strip().lower() != plan.provider:
        raise ValueError("aligned campaign provider does not match plan")
    paths = [Path(job.dataset_path) for job in plan.jobs]
    paths.append(execution_manifest_path)
    normalized = tuple(path.resolve(strict=False) for path in paths)
    if len(set(normalized)) != len(normalized):
        raise ValueError("aligned campaign output paths must be unique")
    existing = sorted(str(path) for path in paths if path.exists())
    if existing:
        raise FileExistsError(
            f"aligned campaign refuses to overwrite existing artifact: {existing[0]}"
        )

    created_paths: list[Path] = []
    results: list[AlignedDatasetCampaignJobResult] = []
    try:
        for job in plan.jobs:
            result = _execute_job(plan, job, provider, extracted_at)
            path = Path(job.dataset_path)
            dataset = load_futures_dataset(path)
            created_paths.append(path)
            if dataset.manifest.dataset_id != job.dataset_id:
                raise ValueError("aligned campaign dataset ID does not match plan")
            if dataset.manifest.content_hash != result.content_hash:
                raise ValueError("aligned campaign dataset hash changed after reload")
            results.append(result)

        completed = AlignedDatasetCampaignExecutionResult(
            campaign_id=plan.campaign_id,
            provider=plan.provider,
            plan_path=plan_path.as_posix(),
            warmup_start=plan.warmup_start,
            analysis_start=plan.boundaries.analysis_start,
            train_end=plan.boundaries.train_end,
            validation_end=plan.boundaries.validation_end,
            analysis_end=plan.boundaries.analysis_end,
            jobs=tuple(results),
        )
        write_aligned_dataset_campaign_execution_result(execution_manifest_path, completed)
        created_paths.append(execution_manifest_path)
        verify_aligned_dataset_campaign_execution(plan=plan, result=completed)
        return completed
    except Exception:
        for path in reversed(created_paths):
            with suppress(OSError):
                path.unlink(missing_ok=True)
        raise


def verify_aligned_dataset_campaign_execution(
    *,
    plan: AlignedDatasetCampaignPlan,
    result: AlignedDatasetCampaignExecutionResult,
) -> None:
    """Verify exact plan/result identity and reload every persisted dataset."""

    if result.campaign_id != plan.campaign_id or result.provider != plan.provider:
        raise ValueError("aligned execution identity does not match plan")
    if result.warmup_start != plan.warmup_start:
        raise ValueError("aligned execution warmup boundary does not match plan")
    expected_boundaries = (
        plan.boundaries.analysis_start,
        plan.boundaries.train_end,
        plan.boundaries.validation_end,
        plan.boundaries.analysis_end,
    )
    actual_boundaries = (
        result.analysis_start,
        result.train_end,
        result.validation_end,
        result.analysis_end,
    )
    if actual_boundaries != expected_boundaries:
        raise ValueError("aligned execution split boundaries do not match plan")
    if len(result.jobs) != len(plan.jobs):
        raise ValueError("aligned execution job count does not match plan")
    for job, job_result in zip(plan.jobs, result.jobs, strict=True):
        expected = (
            job.acquisition_order,
            job.symbol,
            job.timeframe,
            job.dataset_id,
            job.dataset_path,
        )
        actual = (
            job_result.acquisition_order,
            job_result.symbol,
            job_result.timeframe,
            job_result.dataset_id,
            job_result.dataset_path,
        )
        if actual != expected:
            raise ValueError("aligned execution job does not match plan")
        dataset = load_futures_dataset(Path(job.dataset_path))
        if dataset.manifest.content_hash != job_result.content_hash:
            raise ValueError("aligned execution persisted dataset hash does not match manifest")
        _verify_dataset_coverage(plan, job, dataset.candles)


def write_aligned_dataset_campaign_execution_result(
    path: Path,
    result: AlignedDatasetCampaignExecutionResult,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result.to_payload(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def load_aligned_dataset_campaign_execution_result(
    path: Path,
) -> AlignedDatasetCampaignExecutionResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("boundaries"), dict):
        raise ValueError("aligned execution payload must be an object")
    boundaries = payload["boundaries"]
    raw_jobs = payload.get("jobs")
    if not isinstance(raw_jobs, list):
        raise ValueError("aligned execution jobs must be a list")
    jobs = tuple(
        AlignedDatasetCampaignJobResult(
            acquisition_order=int(item["acquisition_order"]),
            symbol=str(item["symbol"]),
            timeframe=str(item["timeframe"]),
            dataset_id=str(item["dataset_id"]),
            dataset_path=str(item["dataset_path"]),
            content_hash=str(item["content_hash"]),
            candle_count=int(item["candle_count"]),
            warmup_candle_count=int(item["warmup_candle_count"]),
            first_open_time=datetime.fromisoformat(str(item["first_open_time"])),
            last_close_time=datetime.fromisoformat(str(item["last_close_time"])),
        )
        for item in raw_jobs
        if isinstance(item, dict)
    )
    return AlignedDatasetCampaignExecutionResult(
        schema_version=int(payload["schema_version"]),
        campaign_id=str(payload["campaign_id"]),
        provider=str(payload["provider"]),
        plan_path=str(payload["plan_path"]),
        warmup_start=datetime.fromisoformat(str(payload["warmup_start"])),
        analysis_start=datetime.fromisoformat(str(boundaries["analysis_start"])),
        train_end=datetime.fromisoformat(str(boundaries["train_end"])),
        validation_end=datetime.fromisoformat(str(boundaries["validation_end"])),
        analysis_end=datetime.fromisoformat(str(boundaries["analysis_end"])),
        jobs=jobs,
    )


def _execute_job(
    plan: AlignedDatasetCampaignPlan,
    job: AlignedDatasetCampaignJob,
    provider: HistoricalRangeMarketDataProvider,
    extracted_at: datetime,
) -> AlignedDatasetCampaignJobResult:
    candles = tuple(
        provider.fetch_candles_range(
            job.symbol,
            job.timeframe,
            start_time=plan.warmup_start,
            end_time=plan.boundaries.analysis_end,
        )
    )
    _verify_dataset_coverage(plan, job, candles)
    dataset = build_futures_dataset(
        dataset_id=job.dataset_id,
        candles=candles,
        extracted_at=extracted_at,
    )
    write_futures_dataset(Path(job.dataset_path), dataset)
    warmup_count = sum(candle.close_time <= plan.boundaries.analysis_start for candle in candles)
    return AlignedDatasetCampaignJobResult(
        acquisition_order=job.acquisition_order,
        symbol=job.symbol,
        timeframe=job.timeframe,
        dataset_id=job.dataset_id,
        dataset_path=job.dataset_path,
        content_hash=dataset.manifest.content_hash,
        candle_count=len(candles),
        warmup_candle_count=warmup_count,
        first_open_time=candles[0].open_time,
        last_close_time=candles[-1].close_time,
    )


def _verify_dataset_coverage(
    plan: AlignedDatasetCampaignPlan,
    job: AlignedDatasetCampaignJob,
    candles: tuple[Candle, ...],
) -> None:
    if not candles:
        raise ValueError("aligned campaign dataset is empty")

    expected_step = _TIMEFRAME_SECONDS[job.timeframe]
    for previous, current in pairwise(candles):
        step = int((current.open_time - previous.open_time).total_seconds())
        if step != expected_step:
            raise ValueError("aligned campaign dataset contains a candle gap")

    if len(candles) < job.expected_minimum_candles:
        raise ValueError("aligned campaign dataset is missing expected range candles")
    if candles[0].open_time > plan.warmup_start:
        raise ValueError("aligned campaign dataset does not cover warmup start")
    if candles[-1].close_time < plan.boundaries.analysis_end:
        raise ValueError("aligned campaign dataset does not cover analysis end")

    warmup_count = sum(candle.close_time <= plan.boundaries.analysis_start for candle in candles)
    if warmup_count < plan.warmup_candles:
        raise ValueError("aligned campaign dataset has insufficient warmup candles")


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"aligned execution {name} must be timezone-aware")


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
