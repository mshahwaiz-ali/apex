"""Verified schema-v2 historical signal inputs for futures backtesting."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from apex.backtesting.historical_signal_campaign import (
    HistoricalSignalCampaignInputs,
    load_historical_signal_campaign_inputs,
)
from apex.historical_signals.contracts import (
    HistoricalSignalCampaignManifest,
    HistoricalSignalCampaignRecord,
)
from apex.historical_signals.persistence import (
    hash_file_sha256,
    load_historical_signal_campaign_manifest,
    load_historical_signal_records,
)


@dataclass(frozen=True, slots=True)
class HistoricalBacktestSignalInputs:
    """Fully verified schema-v2 signal artifacts and aligned candle inputs."""

    campaign_inputs: HistoricalSignalCampaignInputs
    manifest: HistoricalSignalCampaignManifest
    records: tuple[HistoricalSignalCampaignRecord, ...]


def load_historical_backtest_signal_inputs(
    *,
    plan_path: Path,
    execution_manifest_path: Path,
    records_path: Path,
    signal_manifest_path: Path,
) -> HistoricalBacktestSignalInputs:
    """Load and verify every artifact required before futures replay starts."""

    campaign_inputs = load_historical_signal_campaign_inputs(
        plan_path=plan_path,
        execution_manifest_path=execution_manifest_path,
    )
    manifest = load_historical_signal_campaign_manifest(signal_manifest_path)
    records = load_historical_signal_records(
        records_path,
        symbol_order=manifest.symbol_order,
        expected_content_hash=manifest.records_content_hash,
    )
    verify_historical_backtest_signal_inputs(
        campaign_inputs=campaign_inputs,
        manifest=manifest,
        records=records,
        plan_path=plan_path,
        execution_manifest_path=execution_manifest_path,
        records_path=records_path,
    )
    return HistoricalBacktestSignalInputs(
        campaign_inputs=campaign_inputs,
        manifest=manifest,
        records=records,
    )


def verify_historical_backtest_signal_inputs(
    *,
    campaign_inputs: HistoricalSignalCampaignInputs,
    manifest: HistoricalSignalCampaignManifest,
    records: tuple[HistoricalSignalCampaignRecord, ...],
    plan_path: Path,
    execution_manifest_path: Path,
    records_path: Path,
) -> None:
    """Reject identity, provenance, count, or path drift before simulation."""

    plan_hash = hash_file_sha256(plan_path)
    execution_hash = hash_file_sha256(execution_manifest_path)
    expected_plan_id = f"aligned-plan-{plan_hash}"
    expected_execution_id = f"aligned-execution-{execution_hash}"

    if Path(manifest.records_path).resolve(strict=False) != records_path.resolve(strict=False):
        raise ValueError("historical signal records path does not match campaign manifest")
    if manifest.campaign_id != campaign_inputs.campaign_id:
        raise ValueError("historical signal campaign ID does not match aligned inputs")
    if manifest.dataset_campaign_plan_id != expected_plan_id:
        raise ValueError("historical signal plan identity does not match plan artifact")
    if manifest.dataset_campaign_execution_id != expected_execution_id:
        raise ValueError("historical signal execution identity does not match execution artifact")
    if manifest.symbol_order != campaign_inputs.symbols:
        raise ValueError("historical signal symbol order does not match aligned inputs")
    if manifest.record_count != len(records):
        raise ValueError("historical signal record count does not match campaign manifest")

    symbol_counts = Counter(record.symbol for record in records)
    if manifest.counts_by_symbol != tuple(
        (symbol, symbol_counts[symbol]) for symbol in manifest.symbol_order
    ):
        raise ValueError("historical signal symbol counts do not match loaded records")
    split_counts = Counter(record.split for record in records)
    if manifest.counts_by_split != tuple(
        (split, split_counts[split]) for split in manifest.split_order
    ):
        raise ValueError("historical signal split counts do not match loaded records")

    expected_sources = {
        symbol: tuple(
            sorted(
                (
                    dataset.timeframe,
                    dataset.dataset_id,
                    dataset.content_hash,
                )
                for dataset in campaign_inputs.source_datasets
                if dataset.symbol == symbol
            )
        )
        for symbol in campaign_inputs.symbols
    }
    for record in records:
        if record.campaign_id != manifest.campaign_id:
            raise ValueError("historical signal record campaign ID drift detected")
        if record.dataset_campaign_plan_id != expected_plan_id:
            raise ValueError("historical signal record plan identity drift detected")
        if record.dataset_campaign_execution_id != expected_execution_id:
            raise ValueError("historical signal record execution identity drift detected")
        if record.parent_dataset_id != expected_plan_id or record.parent_dataset_hash != plan_hash:
            raise ValueError("historical signal record parent dataset drift detected")
        if record.assumptions_hash != manifest.assumptions_hash:
            raise ValueError("historical signal record assumptions drift detected")
        actual_sources = tuple(
            (source.timeframe, source.dataset_id, source.content_hash)
            for source in record.source_datasets
        )
        if actual_sources != expected_sources[record.symbol]:
            raise ValueError("historical signal record source dataset drift detected")
