"""Aligned historical replay conversion and completed campaign persistence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from apex.application.historical_signal_generation import (
    HistoricalSignalRecord,
    generate_historical_signals,
)
from apex.backtesting.historical_signal_campaign import (
    HistoricalSignalCampaignInputs,
    HistoricalSourceDataset,
    load_historical_signal_campaign_inputs,
)
from apex.backtesting.historical_signal_replay import HistoricalSignalSplit
from apex.historical_signals.contracts import (
    HistoricalSignalCampaignManifest,
    HistoricalSignalCampaignRecord,
    HistoricalSignalSourceDataset,
    derive_historical_signal_record_id,
)
from apex.historical_signals.persistence import (
    hash_file_sha256,
    persist_completed_historical_signal_campaign,
)

_SPLIT_ORDER = {
    HistoricalSignalSplit.TRAIN: 0,
    HistoricalSignalSplit.VALIDATION: 1,
    HistoricalSignalSplit.FINAL_TEST: 2,
}


def derive_historical_signal_assumptions_hash(
    assumptions: Mapping[str, object],
) -> str:
    """Hash canonical replay assumptions without environment-dependent state."""

    serialized = json.dumps(
        _canonicalize_mapping(assumptions),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def generate_and_persist_historical_signal_campaign(
    *,
    plan_path: Path,
    execution_manifest_path: Path,
    records_path: Path,
    manifest_path: Path,
    assumptions: Mapping[str, object],
    candle_limit: int = 200,
) -> HistoricalSignalCampaignManifest:
    """Verify aligned artifacts, replay them, convert records, and persist atomically."""

    inputs = load_historical_signal_campaign_inputs(
        plan_path=plan_path,
        execution_manifest_path=execution_manifest_path,
    )
    assumptions_hash = derive_historical_signal_assumptions_hash(assumptions)
    generated = generate_historical_signals(
        inputs=inputs,
        candle_limit=candle_limit,
    )
    plan_hash = hash_file_sha256(plan_path)
    execution_hash = hash_file_sha256(execution_manifest_path)
    dataset_campaign_plan_id = f"aligned-plan-{plan_hash}"
    dataset_campaign_execution_id = f"aligned-execution-{execution_hash}"
    converted = tuple(
        sorted(
            (
                _convert_record(
                    record=record,
                    inputs=inputs,
                    dataset_campaign_plan_id=dataset_campaign_plan_id,
                    dataset_campaign_execution_id=dataset_campaign_execution_id,
                    parent_dataset_hash=plan_hash,
                    assumptions_hash=assumptions_hash,
                    required_context_candles=candle_limit,
                )
                for record in generated.records
            ),
            key=lambda record: (
                inputs.symbols.index(record.symbol),
                _SPLIT_ORDER[record.split],
                record.decision_time,
                record.signal_record_id,
            ),
        )
    )
    return persist_completed_historical_signal_campaign(
        records_path=records_path,
        manifest_path=manifest_path,
        records=converted,
        campaign_id=inputs.campaign_id,
        dataset_campaign_plan_id=dataset_campaign_plan_id,
        dataset_campaign_execution_id=dataset_campaign_execution_id,
        assumptions_hash=assumptions_hash,
        symbol_order=inputs.symbols,
    )


def _convert_record(
    *,
    record: HistoricalSignalRecord,
    inputs: HistoricalSignalCampaignInputs,
    dataset_campaign_plan_id: str,
    dataset_campaign_execution_id: str,
    parent_dataset_hash: str,
    assumptions_hash: str,
    required_context_candles: int,
) -> HistoricalSignalCampaignRecord:
    sources = tuple(
        dataset for dataset in inputs.source_datasets if dataset.symbol == record.symbol
    )
    if not sources:
        raise ValueError("historical replay record has no source datasets")
    primary = _primary_source(sources, inputs.timeframes)
    bindings = tuple(
        HistoricalSignalSourceDataset(
            timeframe=dataset.timeframe,
            dataset_id=dataset.dataset_id,
            content_hash=dataset.content_hash,
        )
        for dataset in sorted(sources, key=lambda item: item.timeframe)
    )
    signal_record_id = derive_historical_signal_record_id(
        campaign_id=record.campaign_id,
        symbol=record.symbol,
        split=record.split,
        decision_time=record.decision_time,
        source_dataset_hash=primary.content_hash,
        assumptions_hash=assumptions_hash,
    )
    return HistoricalSignalCampaignRecord(
        signal_record_id=signal_record_id,
        campaign_id=record.campaign_id,
        dataset_campaign_plan_id=dataset_campaign_plan_id,
        dataset_campaign_execution_id=dataset_campaign_execution_id,
        symbol=record.symbol,
        timeframe=primary.timeframe,
        split=record.split,
        decision_time=record.decision_time,
        parent_dataset_id=dataset_campaign_plan_id,
        parent_dataset_hash=parent_dataset_hash,
        source_dataset_id=primary.dataset_id,
        source_dataset_hash=primary.content_hash,
        source_datasets=bindings,
        assumptions_hash=assumptions_hash,
        required_context_candles=required_context_candles,
        accepted=record.accepted,
        analysis=dict(record.payload),
        unavailable_optional_data=record.unavailable_optional_data,
        failure_reason=record.failure_reason,
    )


def _primary_source(
    sources: tuple[HistoricalSourceDataset, ...],
    timeframes: tuple[str, ...],
) -> HistoricalSourceDataset:
    by_timeframe = {dataset.timeframe: dataset for dataset in sources}
    for timeframe in timeframes:
        if timeframe in by_timeframe:
            return by_timeframe[timeframe]
    raise ValueError("historical replay source matrix does not match campaign timeframes")


def _canonicalize_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return {
        str(key): _canonicalize_value(item)
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
    }


def _canonicalize_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _canonicalize_mapping(value)
    if isinstance(value, tuple):
        return [_canonicalize_value(item) for item in value]
    if isinstance(value, list):
        return [_canonicalize_value(item) for item in value]
    return value
