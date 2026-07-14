"""Timestamp-aligned multi-timeframe historical dataset campaigns."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

from apex.backtesting.dataset_campaign import normalize_campaign_timeframes
from apex.backtesting.dataset_split import FuturesDatasetSplitRatios

ALIGNED_DATASET_CAMPAIGN_SCHEMA_VERSION: Final = 1
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
class AlignedDatasetSplitBoundaries:
    """Common decision-time split boundaries shared by every timeframe."""

    analysis_start: datetime
    train_end: datetime
    validation_end: datetime
    analysis_end: datetime

    def __post_init__(self) -> None:
        for name in ("analysis_start", "train_end", "validation_end", "analysis_end"):
            _require_aware(getattr(self, name), name)
        if not self.analysis_start < self.train_end < self.validation_end < self.analysis_end:
            raise ValueError("aligned split boundaries must be strictly increasing")

    def to_payload(self) -> dict[str, str]:
        return {
            "analysis_start": self.analysis_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "validation_end": self.validation_end.isoformat(),
            "analysis_end": self.analysis_end.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class AlignedDatasetCampaignJob:
    """One frozen symbol/timeframe acquisition job."""

    acquisition_order: int
    symbol: str
    timeframe: str
    provider: str
    dataset_id: str
    dataset_path: str
    expected_minimum_candles: int

    def __post_init__(self) -> None:
        if self.acquisition_order < 1:
            raise ValueError("aligned campaign acquisition order must be positive")
        for value in (
            self.symbol,
            self.timeframe,
            self.provider,
            self.dataset_id,
            self.dataset_path,
        ):
            if not value.strip():
                raise ValueError("aligned campaign job fields cannot be empty")
        if self.expected_minimum_candles < 1:
            raise ValueError("aligned campaign expected candle count must be positive")

    def to_payload(self) -> dict[str, object]:
        return {
            "acquisition_order": self.acquisition_order,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "provider": self.provider,
            "dataset_id": self.dataset_id,
            "dataset_path": self.dataset_path,
            "expected_minimum_candles": self.expected_minimum_candles,
        }


@dataclass(frozen=True, slots=True)
class AlignedDatasetCampaignPlan:
    """Frozen common-period acquisition plan for multi-timeframe research."""

    campaign_id: str
    symbols: tuple[str, ...]
    timeframes: tuple[str, ...]
    provider: str
    warmup_candles: int
    warmup_start: datetime
    boundaries: AlignedDatasetSplitBoundaries
    output_directory: str
    split_ratios: FuturesDatasetSplitRatios
    jobs: tuple[AlignedDatasetCampaignJob, ...]
    schema_version: int = ALIGNED_DATASET_CAMPAIGN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != ALIGNED_DATASET_CAMPAIGN_SCHEMA_VERSION:
            raise ValueError("unsupported aligned dataset campaign schema version")
        if (
            not self.campaign_id.strip()
            or not self.provider.strip()
            or not self.output_directory.strip()
        ):
            raise ValueError("aligned campaign fields cannot be empty")
        if self.warmup_candles < 40:
            raise ValueError("aligned campaign warmup must be at least 40 candles")
        _require_aware(self.warmup_start, "warmup_start")
        expected_warmup_start = self.boundaries.analysis_start - timedelta(
            seconds=max(_TIMEFRAME_SECONDS[item] for item in self.timeframes) * self.warmup_candles
        )
        if self.warmup_start != expected_warmup_start:
            raise ValueError("aligned campaign warmup start does not match highest timeframe")
        if self.symbols != tuple(sorted(self.symbols)) or len(set(self.symbols)) != len(
            self.symbols
        ):
            raise ValueError("aligned campaign symbols must be unique and sorted")
        if self.timeframes != normalize_campaign_timeframes(self.timeframes):
            raise ValueError("aligned campaign timeframes must use canonical order")
        expected_pairs = tuple(
            (symbol, timeframe) for symbol in self.symbols for timeframe in self.timeframes
        )
        actual_pairs = tuple((job.symbol, job.timeframe) for job in self.jobs)
        if actual_pairs != expected_pairs:
            raise ValueError("aligned campaign jobs must match the frozen symbol/timeframe matrix")
        if tuple(job.acquisition_order for job in self.jobs) != tuple(range(1, len(self.jobs) + 1)):
            raise ValueError("aligned campaign acquisition order must be contiguous")
        if len({job.dataset_id for job in self.jobs}) != len(self.jobs):
            raise ValueError("aligned campaign dataset IDs must be unique")
        if len({job.dataset_path for job in self.jobs}) != len(self.jobs):
            raise ValueError("aligned campaign dataset paths must be unique")
        for job in self.jobs:
            if job.provider != self.provider:
                raise ValueError("aligned campaign job provider does not match plan")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "campaign_id": self.campaign_id,
            "symbols": list(self.symbols),
            "timeframes": list(self.timeframes),
            "provider": self.provider,
            "warmup_candles": self.warmup_candles,
            "warmup_start": self.warmup_start.isoformat(),
            "boundaries": self.boundaries.to_payload(),
            "output_directory": self.output_directory,
            "split_ratios": self.split_ratios.to_payload(),
            "jobs": [job.to_payload() for job in self.jobs],
        }


def plan_aligned_dataset_campaign(
    *,
    campaign_id: str,
    symbols: tuple[str, ...],
    timeframes: tuple[str, ...],
    provider: str,
    analysis_start: datetime,
    analysis_end: datetime,
    output_directory: Path,
    warmup_candles: int = 200,
    split_ratios: FuturesDatasetSplitRatios | None = None,
) -> AlignedDatasetCampaignPlan:
    """Build a deterministic common-period acquisition plan."""

    _require_aware(analysis_start, "analysis_start")
    _require_aware(analysis_end, "analysis_end")
    if analysis_start >= analysis_end:
        raise ValueError("analysis start must be before analysis end")
    if warmup_candles < 40:
        raise ValueError("warmup candles must be at least 40")
    normalized_symbols = tuple(sorted(_normalize_symbol(item) for item in symbols))
    if not normalized_symbols or len(set(normalized_symbols)) != len(normalized_symbols):
        raise ValueError("aligned campaign symbols must be non-empty and unique")
    normalized_timeframes = normalize_campaign_timeframes(timeframes)
    normalized_provider = provider.strip().lower()
    if not normalized_provider:
        raise ValueError("aligned campaign provider cannot be empty")
    ratios = split_ratios or FuturesDatasetSplitRatios()
    boundaries = _build_boundaries(analysis_start, analysis_end, ratios)
    highest_seconds = max(_TIMEFRAME_SECONDS[item] for item in normalized_timeframes)
    warmup_start = analysis_start - timedelta(seconds=highest_seconds * warmup_candles)
    normalized_campaign_id = _identifier_part(campaign_id)
    normalized_output = _normalize_path(output_directory)
    total_seconds = (analysis_end - warmup_start).total_seconds()
    matrix = tuple(
        (symbol, timeframe) for symbol in normalized_symbols for timeframe in normalized_timeframes
    )
    jobs = tuple(
        AlignedDatasetCampaignJob(
            acquisition_order=index,
            symbol=symbol,
            timeframe=timeframe,
            provider=normalized_provider,
            dataset_id=f"{normalized_campaign_id}-{_identifier_part(symbol)}-{timeframe}-aligned",
            dataset_path=_normalize_path(
                Path(normalized_output)
                / f"{normalized_campaign_id}-{_identifier_part(symbol)}-{timeframe}-aligned.json"
            ),
            expected_minimum_candles=max(
                1, math.floor(total_seconds / _TIMEFRAME_SECONDS[timeframe])
            ),
        )
        for index, (symbol, timeframe) in enumerate(matrix, start=1)
    )
    return AlignedDatasetCampaignPlan(
        campaign_id=normalized_campaign_id,
        symbols=normalized_symbols,
        timeframes=normalized_timeframes,
        provider=normalized_provider,
        warmup_candles=warmup_candles,
        warmup_start=warmup_start,
        boundaries=boundaries,
        output_directory=normalized_output,
        split_ratios=ratios,
        jobs=jobs,
    )


def write_aligned_dataset_campaign_plan(path: Path, plan: AlignedDatasetCampaignPlan) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(plan.to_payload(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def load_aligned_dataset_campaign_plan(path: Path) -> AlignedDatasetCampaignPlan:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("aligned campaign payload must be an object")
    raw_boundaries = payload["boundaries"]
    raw_ratios = payload["split_ratios"]
    raw_jobs = payload["jobs"]
    if (
        not isinstance(raw_boundaries, dict)
        or not isinstance(raw_ratios, dict)
        or not isinstance(raw_jobs, list)
    ):
        raise ValueError("aligned campaign payload contains invalid objects")
    boundaries = AlignedDatasetSplitBoundaries(
        analysis_start=datetime.fromisoformat(str(raw_boundaries["analysis_start"])),
        train_end=datetime.fromisoformat(str(raw_boundaries["train_end"])),
        validation_end=datetime.fromisoformat(str(raw_boundaries["validation_end"])),
        analysis_end=datetime.fromisoformat(str(raw_boundaries["analysis_end"])),
    )
    ratios = FuturesDatasetSplitRatios(
        train=float(raw_ratios["train"]),
        validation=float(raw_ratios["validation"]),
        final_test=float(raw_ratios["final_test"]),
    )
    jobs = tuple(
        AlignedDatasetCampaignJob(
            acquisition_order=int(item["acquisition_order"]),
            symbol=str(item["symbol"]),
            timeframe=str(item["timeframe"]),
            provider=str(item["provider"]),
            dataset_id=str(item["dataset_id"]),
            dataset_path=str(item["dataset_path"]),
            expected_minimum_candles=int(item["expected_minimum_candles"]),
        )
        for item in raw_jobs
        if isinstance(item, dict)
    )
    return AlignedDatasetCampaignPlan(
        schema_version=int(payload["schema_version"]),
        campaign_id=str(payload["campaign_id"]),
        symbols=tuple(str(item) for item in payload["symbols"]),
        timeframes=tuple(str(item) for item in payload["timeframes"]),
        provider=str(payload["provider"]),
        warmup_candles=int(payload["warmup_candles"]),
        warmup_start=datetime.fromisoformat(str(payload["warmup_start"])),
        boundaries=boundaries,
        output_directory=str(payload["output_directory"]),
        split_ratios=ratios,
        jobs=jobs,
    )


def _build_boundaries(
    analysis_start: datetime,
    analysis_end: datetime,
    ratios: FuturesDatasetSplitRatios,
) -> AlignedDatasetSplitBoundaries:
    duration = analysis_end - analysis_start
    train_end = analysis_start + duration * ratios.train
    validation_end = train_end + duration * ratios.validation
    return AlignedDatasetSplitBoundaries(
        analysis_start=analysis_start,
        train_end=train_end,
        validation_end=validation_end,
        analysis_end=analysis_end,
    )


def _normalize_symbol(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("aligned campaign symbol cannot be empty")
    return normalized


def _identifier_part(value: str) -> str:
    normalized = "".join(character.lower() for character in value.strip() if character.isalnum())
    if not normalized:
        raise ValueError("aligned campaign identifier component cannot be empty")
    return normalized


def _normalize_path(path: Path) -> str:
    return Path(os.path.normpath(str(path))).as_posix()


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"aligned campaign {name.replace('_', ' ')} must be timezone-aware")
