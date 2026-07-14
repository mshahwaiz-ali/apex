"""Fail-fast execution of frozen historical futures dataset campaigns."""

from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Final

from apex.backtesting.dataset import (
    FuturesCandleDataset,
    load_futures_dataset,
    write_futures_dataset,
)
from apex.backtesting.dataset_acquisition import acquire_futures_dataset
from apex.backtesting.dataset_campaign import (
    FuturesDatasetCampaignJob,
    FuturesDatasetCampaignPlan,
)
from apex.backtesting.dataset_split import (
    FuturesDatasetSplitRatios,
    FuturesDatasetSplitSet,
    load_and_verify_futures_dataset_split,
    split_futures_dataset,
    write_futures_dataset_split_manifest,
)
from apex.data.providers.base import MarketDataProvider

FUTURES_DATASET_CAMPAIGN_EXECUTION_SCHEMA_VERSION: Final = 1


class FuturesDatasetCampaignExecutionStatus(StrEnum):
    """Terminal campaign-execution status."""

    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class FuturesDatasetCampaignArtifactResult:
    """Verified identity, hash, count, and path for one dataset artifact."""

    dataset_id: str
    content_hash: str
    candle_count: int
    path: str

    def __post_init__(self) -> None:
        if not self.dataset_id.strip():
            raise ValueError("campaign execution dataset ID cannot be empty")
        if not _is_sha256(self.content_hash):
            raise ValueError("campaign execution dataset hash must be a SHA-256 hex digest")
        if self.candle_count < 1:
            raise ValueError("campaign execution dataset candle count must be positive")
        if not self.path.strip():
            raise ValueError("campaign execution dataset path cannot be empty")

    def to_payload(self) -> dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "content_hash": self.content_hash,
            "candle_count": self.candle_count,
            "path": self.path,
        }


@dataclass(frozen=True, slots=True)
class FuturesDatasetCampaignJobExecutionResult:
    """Result of one frozen campaign job."""

    acquisition_order: int
    symbol: str
    timeframe: str
    provider: str
    status: FuturesDatasetCampaignExecutionStatus
    parent: FuturesDatasetCampaignArtifactResult | None
    train: FuturesDatasetCampaignArtifactResult | None
    validation: FuturesDatasetCampaignArtifactResult | None
    final_test: FuturesDatasetCampaignArtifactResult | None
    split_manifest_path: str
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.acquisition_order < 1:
            raise ValueError("campaign execution acquisition order must be positive")
        for name in ("symbol", "timeframe", "provider", "split_manifest_path"):
            if not getattr(self, name).strip():
                raise ValueError(f"campaign execution job {name.replace('_', ' ')} cannot be empty")

        artifacts = (self.parent, self.train, self.validation, self.final_test)
        if self.status is FuturesDatasetCampaignExecutionStatus.COMPLETED:
            if any(artifact is None for artifact in artifacts):
                raise ValueError("completed campaign job requires every dataset artifact")
            if self.failure_reason is not None:
                raise ValueError("completed campaign job cannot contain a failure reason")
        else:
            if not self.failure_reason or not self.failure_reason.strip():
                raise ValueError("failed campaign job requires a failure reason")

    def to_payload(self) -> dict[str, object]:
        return {
            "acquisition_order": self.acquisition_order,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "provider": self.provider,
            "status": self.status.value,
            "datasets": {
                "parent": _artifact_payload(self.parent),
                "train": _artifact_payload(self.train),
                "validation": _artifact_payload(self.validation),
                "final_test": _artifact_payload(self.final_test),
            },
            "split_manifest_path": self.split_manifest_path,
            "failure_reason": self.failure_reason,
        }


@dataclass(frozen=True, slots=True)
class FuturesDatasetCampaignExecutionResult:
    """Immutable terminal result for one campaign execution attempt."""

    campaign_id: str
    provider: str
    total_planned_jobs: int
    completed_jobs: int
    failed_jobs: int
    status: FuturesDatasetCampaignExecutionStatus
    jobs: tuple[FuturesDatasetCampaignJobExecutionResult, ...]
    failure_reason: str | None = None
    schema_version: int = FUTURES_DATASET_CAMPAIGN_EXECUTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.campaign_id.strip():
            raise ValueError("campaign execution campaign ID cannot be empty")
        if not self.provider.strip():
            raise ValueError("campaign execution provider cannot be empty")
        if self.total_planned_jobs < 1:
            raise ValueError("campaign execution requires at least one planned job")
        if self.completed_jobs < 0 or self.failed_jobs < 0:
            raise ValueError("campaign execution job counts cannot be negative")
        if self.completed_jobs + self.failed_jobs > self.total_planned_jobs:
            raise ValueError("campaign execution job counts exceed planned jobs")
        if self.schema_version != FUTURES_DATASET_CAMPAIGN_EXECUTION_SCHEMA_VERSION:
            raise ValueError("unsupported futures dataset campaign execution schema version")

        orders = tuple(job.acquisition_order for job in self.jobs)
        if orders != tuple(range(1, len(self.jobs) + 1)):
            raise ValueError("campaign execution jobs must remain in acquisition order")

        completed = sum(
            job.status is FuturesDatasetCampaignExecutionStatus.COMPLETED for job in self.jobs
        )
        failed = sum(
            job.status is FuturesDatasetCampaignExecutionStatus.FAILED for job in self.jobs
        )
        if completed != self.completed_jobs or failed != self.failed_jobs:
            raise ValueError("campaign execution result counts do not match job results")

        if self.status is FuturesDatasetCampaignExecutionStatus.COMPLETED:
            if self.completed_jobs != self.total_planned_jobs:
                raise ValueError("completed campaign must complete every planned job")
            if self.failed_jobs != 0:
                raise ValueError("completed campaign cannot contain failed jobs")
            if len(self.jobs) != self.total_planned_jobs:
                raise ValueError("completed campaign must contain every planned job result")
            if self.failure_reason is not None:
                raise ValueError("completed campaign cannot contain a failure reason")
        else:
            if self.failed_jobs < 1:
                raise ValueError("failed campaign must contain a failed job")
            if not self.failure_reason or not self.failure_reason.strip():
                raise ValueError("failed campaign requires a failure reason")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "campaign_id": self.campaign_id,
            "provider": self.provider,
            "total_planned_jobs": self.total_planned_jobs,
            "completed_jobs": self.completed_jobs,
            "failed_jobs": self.failed_jobs,
            "status": self.status.value,
            "failure_reason": self.failure_reason,
            "jobs": [job.to_payload() for job in self.jobs],
        }


class FuturesDatasetCampaignExecutionError(RuntimeError):
    """Fail-fast campaign error carrying its immutable failure result."""

    def __init__(
        self,
        message: str,
        *,
        result: FuturesDatasetCampaignExecutionResult,
    ) -> None:
        super().__init__(message)
        self.result = result


def execute_futures_dataset_campaign(
    *,
    plan: FuturesDatasetCampaignPlan,
    provider: MarketDataProvider,
    configured_provider: str,
    extracted_at: datetime,
    execution_manifest_path: Path,
) -> FuturesDatasetCampaignExecutionResult:
    """Execute one frozen campaign strictly in its manifest acquisition order."""

    normalized_configured_provider = configured_provider.strip().lower()
    if not normalized_configured_provider:
        raise ValueError("configured campaign provider cannot be empty")
    if plan.provider != normalized_configured_provider:
        raise ValueError(
            "campaign provider does not match configured provider: "
            f"plan={plan.provider}, configured={normalized_configured_provider}"
        )
    if extracted_at.tzinfo is None or extracted_at.utcoffset() is None:
        raise ValueError("campaign execution extraction time must be timezone-aware")

    _reject_pre_existing_artifacts(
        plan=plan,
        execution_manifest_path=execution_manifest_path,
    )

    completed: list[FuturesDatasetCampaignJobExecutionResult] = []
    created_paths: list[Path] = []

    for job in plan.jobs:
        try:
            result = _execute_job(
                plan=plan,
                job=job,
                provider=provider,
                extracted_at=extracted_at,
                created_paths=created_paths,
            )
        except Exception as exc:
            _remove_created_paths(created_paths)
            failure_reason = str(exc) or exc.__class__.__name__
            failed_job = FuturesDatasetCampaignJobExecutionResult(
                acquisition_order=job.acquisition_order,
                symbol=job.symbol,
                timeframe=job.timeframe,
                provider=job.provider,
                status=FuturesDatasetCampaignExecutionStatus.FAILED,
                parent=None,
                train=None,
                validation=None,
                final_test=None,
                split_manifest_path=job.split_manifest_path,
                failure_reason=failure_reason,
            )
            failure = FuturesDatasetCampaignExecutionResult(
                campaign_id=plan.campaign_id,
                provider=plan.provider,
                total_planned_jobs=len(plan.jobs),
                completed_jobs=len(completed),
                failed_jobs=1,
                status=FuturesDatasetCampaignExecutionStatus.FAILED,
                jobs=tuple((*completed, failed_job)),
                failure_reason=(
                    f"campaign job {job.acquisition_order} failed for "
                    f"{job.symbol}: {failure_reason}"
                ),
            )
            raise FuturesDatasetCampaignExecutionError(
                failure.failure_reason or "campaign execution failed",
                result=failure,
            ) from exc

        completed.append(result)

    return FuturesDatasetCampaignExecutionResult(
        campaign_id=plan.campaign_id,
        provider=plan.provider,
        total_planned_jobs=len(plan.jobs),
        completed_jobs=len(completed),
        failed_jobs=0,
        status=FuturesDatasetCampaignExecutionStatus.COMPLETED,
        jobs=tuple(completed),
    )


def write_futures_dataset_campaign_execution_result(
    path: Path,
    result: FuturesDatasetCampaignExecutionResult,
) -> None:
    """Atomically persist a completely successful campaign execution."""

    if result.status is not FuturesDatasetCampaignExecutionStatus.COMPLETED:
        raise ValueError("only completed campaign executions may be persisted")

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_futures_dataset_campaign_execution_result(
    path: Path,
) -> FuturesDatasetCampaignExecutionResult:
    """Load and fully validate a successful campaign execution manifest."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("campaign execution manifest must be an object")

    raw_jobs = payload.get("jobs")
    if not isinstance(raw_jobs, list):
        raise ValueError("campaign execution jobs must be a list")

    jobs = tuple(_load_job_result(raw_job) for raw_job in raw_jobs)
    result = FuturesDatasetCampaignExecutionResult(
        schema_version=_as_int(payload["schema_version"], "schema_version"),
        campaign_id=str(payload["campaign_id"]),
        provider=str(payload["provider"]),
        total_planned_jobs=_as_int(
            payload["total_planned_jobs"],
            "total_planned_jobs",
        ),
        completed_jobs=_as_int(payload["completed_jobs"], "completed_jobs"),
        failed_jobs=_as_int(payload["failed_jobs"], "failed_jobs"),
        status=FuturesDatasetCampaignExecutionStatus(str(payload["status"])),
        jobs=jobs,
        failure_reason=_optional_string(payload.get("failure_reason")),
    )
    if result.status is not FuturesDatasetCampaignExecutionStatus.COMPLETED:
        raise ValueError("persisted campaign execution manifest must be completed")
    return result


def verify_futures_dataset_campaign_execution(
    *,
    plan: FuturesDatasetCampaignPlan,
    result: FuturesDatasetCampaignExecutionResult,
) -> None:
    """Verify a completed result against its frozen plan and persisted artifacts."""

    if result.status is not FuturesDatasetCampaignExecutionStatus.COMPLETED:
        raise ValueError("campaign execution verification requires a completed result")
    if result.campaign_id != plan.campaign_id:
        raise ValueError("campaign execution campaign ID does not match plan")
    if result.provider != plan.provider:
        raise ValueError("campaign execution provider does not match plan")
    if result.total_planned_jobs != len(plan.jobs):
        raise ValueError("campaign execution planned-job count does not match plan")
    if len(result.jobs) != len(plan.jobs):
        raise ValueError("campaign execution job results do not match plan")

    for job, job_result in zip(plan.jobs, result.jobs, strict=True):
        _verify_job_result_against_plan(job=job, result=job_result)
        parent, split_set = load_and_verify_futures_dataset_split(
            parent_path=Path(job.parent_dataset_path),
            train_path=Path(job.train_dataset_path),
            validation_path=Path(job.validation_dataset_path),
            final_test_path=Path(job.final_test_dataset_path),
            manifest_path=Path(job.split_manifest_path),
        )
        _verify_loaded_result(
            job=job,
            result=job_result,
            parent=parent,
            split_set=split_set,
        )


def _execute_job(
    *,
    plan: FuturesDatasetCampaignPlan,
    job: FuturesDatasetCampaignJob,
    provider: MarketDataProvider,
    extracted_at: datetime,
    created_paths: list[Path],
) -> FuturesDatasetCampaignJobExecutionResult:
    parent = acquire_futures_dataset(
        provider=provider,
        symbol=job.symbol,
        timeframe=job.timeframe,
        candle_limit=job.candle_count,
        extracted_at=extracted_at,
        dataset_id=job.parent_dataset_id,
    )
    _verify_acquired_parent(job=job, parent=parent)

    parent_path = Path(job.parent_dataset_path)
    write_futures_dataset(parent_path, parent)
    created_paths.append(parent_path)

    verified_parent = load_futures_dataset(parent_path)
    _verify_acquired_parent(job=job, parent=verified_parent)

    split_set = split_futures_dataset(
        verified_parent,
        ratios=FuturesDatasetSplitRatios(
            train=plan.split_ratios.train,
            validation=plan.split_ratios.validation,
            final_test=plan.split_ratios.final_test,
        ),
    )
    _verify_split_ids(job=job, split_set=split_set)

    train_path = Path(job.train_dataset_path)
    validation_path = Path(job.validation_dataset_path)
    final_test_path = Path(job.final_test_dataset_path)
    split_manifest_path = Path(job.split_manifest_path)

    write_futures_dataset(train_path, split_set.train)
    created_paths.append(train_path)
    write_futures_dataset(validation_path, split_set.validation)
    created_paths.append(validation_path)
    write_futures_dataset(final_test_path, split_set.final_test)
    created_paths.append(final_test_path)
    write_futures_dataset_split_manifest(split_manifest_path, split_set.manifest)
    created_paths.append(split_manifest_path)

    loaded_parent, loaded_split_set = load_and_verify_futures_dataset_split(
        parent_path=parent_path,
        train_path=train_path,
        validation_path=validation_path,
        final_test_path=final_test_path,
        manifest_path=split_manifest_path,
    )
    _verify_split_ids(job=job, split_set=loaded_split_set)

    result = FuturesDatasetCampaignJobExecutionResult(
        acquisition_order=job.acquisition_order,
        symbol=job.symbol,
        timeframe=job.timeframe,
        provider=job.provider,
        status=FuturesDatasetCampaignExecutionStatus.COMPLETED,
        parent=_artifact_result(loaded_parent, job.parent_dataset_path),
        train=_artifact_result(loaded_split_set.train, job.train_dataset_path),
        validation=_artifact_result(
            loaded_split_set.validation,
            job.validation_dataset_path,
        ),
        final_test=_artifact_result(
            loaded_split_set.final_test,
            job.final_test_dataset_path,
        ),
        split_manifest_path=job.split_manifest_path,
    )
    _verify_loaded_result(
        job=job,
        result=result,
        parent=loaded_parent,
        split_set=loaded_split_set,
    )
    return result


def _verify_acquired_parent(
    *,
    job: FuturesDatasetCampaignJob,
    parent: FuturesCandleDataset,
) -> None:
    manifest = parent.manifest
    if manifest.dataset_id != job.parent_dataset_id:
        raise ValueError("acquired parent dataset ID does not match campaign plan")
    if manifest.symbol != job.symbol:
        raise ValueError("acquired parent symbol does not match campaign plan")
    if manifest.timeframe != job.timeframe:
        raise ValueError("acquired parent timeframe does not match campaign plan")
    if manifest.source.lower().strip() != job.provider:
        raise ValueError("acquired parent provider does not match campaign plan")


def _verify_split_ids(
    *,
    job: FuturesDatasetCampaignJob,
    split_set: FuturesDatasetSplitSet,
) -> None:
    actual = (
        split_set.train.manifest.dataset_id,
        split_set.validation.manifest.dataset_id,
        split_set.final_test.manifest.dataset_id,
    )
    expected = (
        job.train_dataset_id,
        job.validation_dataset_id,
        job.final_test_dataset_id,
    )
    if actual != expected:
        raise ValueError("generated child dataset IDs do not match campaign plan")


def _verify_loaded_result(
    *,
    job: FuturesDatasetCampaignJob,
    result: FuturesDatasetCampaignJobExecutionResult,
    parent: FuturesCandleDataset,
    split_set: FuturesDatasetSplitSet,
) -> None:
    _verify_job_result_against_plan(job=job, result=result)

    expected = (
        _artifact_result(parent, job.parent_dataset_path),
        _artifact_result(split_set.train, job.train_dataset_path),
        _artifact_result(split_set.validation, job.validation_dataset_path),
        _artifact_result(split_set.final_test, job.final_test_dataset_path),
    )
    actual = (
        result.parent,
        result.train,
        result.validation,
        result.final_test,
    )
    if actual != expected:
        raise ValueError("campaign execution result does not match reloaded artifacts")


def _verify_job_result_against_plan(
    *,
    job: FuturesDatasetCampaignJob,
    result: FuturesDatasetCampaignJobExecutionResult,
) -> None:
    if result.acquisition_order != job.acquisition_order:
        raise ValueError("campaign execution acquisition order does not match plan")
    if result.symbol != job.symbol:
        raise ValueError("campaign execution symbol does not match plan")
    if result.timeframe != job.timeframe:
        raise ValueError("campaign execution timeframe does not match plan")
    if result.provider != job.provider:
        raise ValueError("campaign execution provider does not match plan")
    if result.split_manifest_path != job.split_manifest_path:
        raise ValueError("campaign execution split manifest path does not match plan")
    if result.status is not FuturesDatasetCampaignExecutionStatus.COMPLETED:
        raise ValueError("campaign execution job is not completed")

    artifacts = (
        (result.parent, job.parent_dataset_id, job.parent_dataset_path),
        (result.train, job.train_dataset_id, job.train_dataset_path),
        (
            result.validation,
            job.validation_dataset_id,
            job.validation_dataset_path,
        ),
        (
            result.final_test,
            job.final_test_dataset_id,
            job.final_test_dataset_path,
        ),
    )
    for artifact, expected_id, expected_path in artifacts:
        if artifact is None:
            raise ValueError("campaign execution job is missing an artifact result")
        if artifact.dataset_id != expected_id:
            raise ValueError("campaign execution artifact ID does not match plan")
        if artifact.path != expected_path:
            raise ValueError("campaign execution artifact path does not match plan")


def _reject_pre_existing_artifacts(
    *,
    plan: FuturesDatasetCampaignPlan,
    execution_manifest_path: Path,
) -> None:
    paths = [Path(path) for job in plan.jobs for path in job.artifact_paths()]
    paths.append(execution_manifest_path)

    normalized = tuple(path.resolve(strict=False) for path in paths)
    if len(set(normalized)) != len(normalized):
        raise ValueError("campaign execution paths must be unique")

    existing = sorted(str(path) for path in paths if path.exists())
    if existing:
        raise FileExistsError(
            f"campaign execution refuses to overwrite existing artifact: {existing[0]}"
        )


def _remove_created_paths(paths: list[Path]) -> None:
    for path in reversed(paths):
        with suppress(OSError):
            path.unlink(missing_ok=True)


def _artifact_result(
    dataset: FuturesCandleDataset,
    path: str,
) -> FuturesDatasetCampaignArtifactResult:
    return FuturesDatasetCampaignArtifactResult(
        dataset_id=dataset.manifest.dataset_id,
        content_hash=dataset.manifest.content_hash,
        candle_count=dataset.manifest.candle_count,
        path=path,
    )


def _artifact_payload(
    artifact: FuturesDatasetCampaignArtifactResult | None,
) -> dict[str, object] | None:
    return artifact.to_payload() if artifact is not None else None


def _load_job_result(payload: object) -> FuturesDatasetCampaignJobExecutionResult:
    if not isinstance(payload, dict):
        raise ValueError("campaign execution job must be an object")
    raw_datasets = payload.get("datasets")
    if not isinstance(raw_datasets, dict):
        raise ValueError("campaign execution job datasets must be an object")

    return FuturesDatasetCampaignJobExecutionResult(
        acquisition_order=_as_int(
            payload["acquisition_order"],
            "jobs.acquisition_order",
        ),
        symbol=str(payload["symbol"]),
        timeframe=str(payload["timeframe"]),
        provider=str(payload["provider"]),
        status=FuturesDatasetCampaignExecutionStatus(str(payload["status"])),
        parent=_load_artifact(raw_datasets.get("parent"), "parent"),
        train=_load_artifact(raw_datasets.get("train"), "train"),
        validation=_load_artifact(raw_datasets.get("validation"), "validation"),
        final_test=_load_artifact(raw_datasets.get("final_test"), "final_test"),
        split_manifest_path=str(payload["split_manifest_path"]),
        failure_reason=_optional_string(payload.get("failure_reason")),
    )


def _load_artifact(
    payload: object,
    role: str,
) -> FuturesDatasetCampaignArtifactResult | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError(f"campaign execution {role} artifact must be an object")
    return FuturesDatasetCampaignArtifactResult(
        dataset_id=str(payload["dataset_id"]),
        content_hash=str(payload["content_hash"]),
        candle_count=_as_int(
            payload["candle_count"],
            f"datasets.{role}.candle_count",
        ),
        path=str(payload["path"]),
    )


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{field} must be an integer")
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an integer") from exc


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
