"""Verified aligned-campaign inputs for historical Apex signal generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from apex.backtesting.aligned_dataset_campaign import (
    AlignedDatasetCampaignPlan,
    load_aligned_dataset_campaign_plan,
)
from apex.backtesting.aligned_dataset_campaign_execution import (
    AlignedDatasetCampaignExecutionResult,
    load_aligned_dataset_campaign_execution_result,
    verify_aligned_dataset_campaign_execution,
)
from apex.backtesting.dataset import load_futures_dataset
from apex.backtesting.historical_signal_replay import (
    HistoricalCandleSeries,
    HistoricalCandleStore,
    HistoricalReplayBoundaries,
    HistoricalReplayPoint,
    build_replay_points,
)


@dataclass(frozen=True, slots=True)
class HistoricalSourceDataset:
    """Verified provenance for one historical signal source dataset."""

    acquisition_order: int
    symbol: str
    timeframe: str
    dataset_id: str
    dataset_path: str
    content_hash: str
    candle_count: int

    def __post_init__(self) -> None:
        if self.acquisition_order < 1 or self.candle_count < 1:
            raise ValueError("historical source dataset counts must be positive")
        for value in (
            self.symbol,
            self.timeframe,
            self.dataset_id,
            self.dataset_path,
        ):
            if not value.strip():
                raise ValueError("historical source dataset fields cannot be empty")
        if not _is_sha256(self.content_hash):
            raise ValueError("historical source dataset hash must be SHA-256")

    def to_payload(self) -> dict[str, object]:
        """Return deterministic manifest-ready provenance."""

        return {
            "acquisition_order": self.acquisition_order,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "dataset_id": self.dataset_id,
            "dataset_path": self.dataset_path,
            "content_hash": self.content_hash,
            "candle_count": self.candle_count,
        }


@dataclass(frozen=True, slots=True)
class HistoricalSignalCampaignInputs:
    """Fully verified immutable inputs for one historical replay campaign."""

    campaign_id: str
    provider: str
    plan_path: str
    execution_manifest_path: str
    symbols: tuple[str, ...]
    timeframes: tuple[str, ...]
    boundaries: HistoricalReplayBoundaries
    store: HistoricalCandleStore
    source_datasets: tuple[HistoricalSourceDataset, ...]

    def __post_init__(self) -> None:
        for value in (
            self.campaign_id,
            self.provider,
            self.plan_path,
            self.execution_manifest_path,
        ):
            if not value.strip():
                raise ValueError("historical signal campaign input fields cannot be empty")
        if not self.symbols or not self.timeframes:
            raise ValueError("historical signal campaign requires symbols and timeframes")
        if not self.source_datasets:
            raise ValueError("historical signal campaign requires source datasets")

        expected_pairs = tuple(
            (symbol, timeframe) for symbol in self.symbols for timeframe in self.timeframes
        )
        actual_pairs = tuple(
            (dataset.symbol, dataset.timeframe) for dataset in self.source_datasets
        )
        if actual_pairs != expected_pairs:
            raise ValueError("historical source datasets do not match campaign matrix")

        expected_orders = tuple(range(1, len(self.source_datasets) + 1))
        actual_orders = tuple(dataset.acquisition_order for dataset in self.source_datasets)
        if actual_orders != expected_orders:
            raise ValueError("historical source dataset order must be contiguous")

    @property
    def source_dataset_hashes(self) -> tuple[str, ...]:
        """Return source hashes in frozen acquisition order."""

        return tuple(dataset.content_hash for dataset in self.source_datasets)


def load_historical_signal_campaign_inputs(
    *,
    plan_path: Path,
    execution_manifest_path: Path,
) -> HistoricalSignalCampaignInputs:
    """Load and fully verify all aligned artifacts before replay."""

    plan = load_aligned_dataset_campaign_plan(plan_path)
    execution = load_aligned_dataset_campaign_execution_result(execution_manifest_path)

    _verify_execution_plan_path(
        plan_path=plan_path,
        execution=execution,
    )
    verify_aligned_dataset_campaign_execution(
        plan=plan,
        result=execution,
    )

    series: list[HistoricalCandleSeries] = []
    sources: list[HistoricalSourceDataset] = []

    for plan_job, execution_job in zip(
        plan.jobs,
        execution.jobs,
        strict=True,
    ):
        dataset = load_futures_dataset(Path(plan_job.dataset_path))
        manifest = dataset.manifest

        if manifest.dataset_id != plan_job.dataset_id:
            raise ValueError("historical source dataset ID does not match campaign plan")
        if manifest.symbol != plan_job.symbol:
            raise ValueError("historical source dataset symbol does not match campaign plan")
        if manifest.timeframe != plan_job.timeframe:
            raise ValueError("historical source dataset timeframe does not match campaign plan")
        if manifest.source.strip().lower() != plan.provider:
            raise ValueError("historical source dataset provider does not match campaign plan")
        if manifest.content_hash != execution_job.content_hash:
            raise ValueError("historical source dataset hash does not match execution manifest")
        if manifest.candle_count != execution_job.candle_count:
            raise ValueError("historical source candle count does not match execution manifest")
        if manifest.start_time != execution_job.first_open_time:
            raise ValueError("historical source start time does not match execution manifest")
        if manifest.end_time != execution_job.last_close_time:
            raise ValueError("historical source end time does not match execution manifest")

        series.append(
            HistoricalCandleSeries(
                symbol=manifest.symbol,
                timeframe=manifest.timeframe,
                candles=dataset.candles,
            )
        )
        sources.append(
            HistoricalSourceDataset(
                acquisition_order=execution_job.acquisition_order,
                symbol=manifest.symbol,
                timeframe=manifest.timeframe,
                dataset_id=manifest.dataset_id,
                dataset_path=plan_job.dataset_path,
                content_hash=manifest.content_hash,
                candle_count=manifest.candle_count,
            )
        )

    return HistoricalSignalCampaignInputs(
        campaign_id=plan.campaign_id,
        provider=plan.provider,
        plan_path=plan_path.as_posix(),
        execution_manifest_path=execution_manifest_path.as_posix(),
        symbols=plan.symbols,
        timeframes=plan.timeframes,
        boundaries=_replay_boundaries(plan),
        store=HistoricalCandleStore(series),
        source_datasets=tuple(sources),
    )


def _verify_execution_plan_path(
    *,
    plan_path: Path,
    execution: AlignedDatasetCampaignExecutionResult,
) -> None:
    expected = plan_path.resolve(strict=False)
    actual = Path(execution.plan_path).resolve(strict=False)
    if actual != expected:
        raise ValueError("aligned execution manifest does not reference the supplied plan")


def _replay_boundaries(
    plan: AlignedDatasetCampaignPlan,
) -> HistoricalReplayBoundaries:
    return HistoricalReplayBoundaries(
        analysis_start=plan.boundaries.analysis_start,
        train_end=plan.boundaries.train_end,
        validation_end=plan.boundaries.validation_end,
        analysis_end=plan.boundaries.analysis_end,
    )


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


_TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
}


def build_historical_signal_replay_points(
    inputs: HistoricalSignalCampaignInputs,
) -> tuple[HistoricalReplayPoint, ...]:
    """Build the frozen chronological schedule from the finest timeframe."""

    try:
        finest_timeframe = min(
            inputs.timeframes,
            key=_TIMEFRAME_SECONDS.__getitem__,
        )
    except KeyError as exc:
        raise ValueError(f"unsupported historical replay timeframe: {exc.args[0]}") from exc

    reference_symbol = inputs.symbols[0]
    reference_times = _decision_times_for_series(
        inputs=inputs,
        symbol=reference_symbol,
        timeframe=finest_timeframe,
    )

    for symbol in inputs.symbols[1:]:
        actual_times = _decision_times_for_series(
            inputs=inputs,
            symbol=symbol,
            timeframe=finest_timeframe,
        )
        if actual_times != reference_times:
            raise ValueError("historical replay decision timestamps are not aligned across symbols")

    return build_replay_points(
        decision_times=reference_times,
        boundaries=inputs.boundaries,
    )


def _decision_times_for_series(
    *,
    inputs: HistoricalSignalCampaignInputs,
    symbol: str,
    timeframe: str,
) -> tuple[datetime, ...]:
    candles = inputs.store.candles_for(symbol, timeframe)
    decision_times = tuple(
        candle.close_time
        for candle in candles
        if (inputs.boundaries.analysis_start <= candle.close_time < inputs.boundaries.analysis_end)
    )
    if not decision_times:
        raise ValueError("historical replay schedule contains no analysis timestamps")
    return decision_times
