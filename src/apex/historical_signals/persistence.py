"""Atomic JSONL and JSON persistence for completed historical signal campaigns."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from apex.backtesting.historical_signal_replay import HistoricalSignalSplit
from apex.historical_signals.contracts import (
    HistoricalSignalCampaignManifest,
    HistoricalSignalCampaignRecord,
    HistoricalSignalSourceDataset,
    derive_historical_signal_campaign_id,
    validate_historical_signal_record_sequence,
)


class HistoricalSignalPersistenceError(RuntimeError):
    """Raised when completed campaign persistence cannot be verified."""


def write_historical_signal_records(
    path: Path,
    records: Sequence[HistoricalSignalCampaignRecord],
    *,
    symbol_order: tuple[str, ...],
) -> str:
    """Atomically write deterministic JSONL and return its SHA-256 hash."""

    validate_historical_signal_record_sequence(records, symbol_order=symbol_order)
    _reject_existing_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            for record in records:
                stream.write(
                    json.dumps(
                        record.to_payload(),
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                    )
                )
                stream.write("\n")
        temporary.replace(path)
    except Exception:
        with suppress(FileNotFoundError):
            temporary.unlink()
        raise
    return hash_file_sha256(path)


def load_historical_signal_records(
    path: Path,
    *,
    symbol_order: tuple[str, ...],
    expected_content_hash: str | None = None,
) -> tuple[HistoricalSignalCampaignRecord, ...]:
    """Load, validate, order-check, and optionally hash-check one JSONL artifact."""

    if expected_content_hash is not None and hash_file_sha256(path) != expected_content_hash:
        raise ValueError("historical signal records content hash does not match manifest")
    records: list[HistoricalSignalCampaignRecord] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw_line.strip():
            raise ValueError(f"historical signal JSONL contains blank line {line_number}")
        payload = json.loads(raw_line)
        if not isinstance(payload, dict):
            raise ValueError(f"historical signal JSONL line {line_number} must be an object")
        records.append(_load_record(payload))
    result = tuple(records)
    validate_historical_signal_record_sequence(result, symbol_order=symbol_order)
    return result


def write_historical_signal_campaign_manifest(
    path: Path,
    manifest: HistoricalSignalCampaignManifest,
) -> None:
    """Atomically persist one completed signal campaign manifest."""

    _reject_existing_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(manifest.to_payload(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    except Exception:
        with suppress(FileNotFoundError):
            temporary.unlink()
        raise


def load_historical_signal_campaign_manifest(
    path: Path,
) -> HistoricalSignalCampaignManifest:
    """Load and fully validate one completed campaign manifest."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("historical signal campaign manifest must be an object")
    raw_symbol_counts = _require_list(payload, "counts_by_symbol")
    raw_split_counts = _require_list(payload, "counts_by_split")
    return HistoricalSignalCampaignManifest(
        schema_version=_as_int(payload["schema_version"], "schema_version"),
        signal_campaign_id=str(payload["signal_campaign_id"]),
        campaign_id=str(payload["campaign_id"]),
        dataset_campaign_plan_id=str(payload["dataset_campaign_plan_id"]),
        dataset_campaign_execution_id=str(payload["dataset_campaign_execution_id"]),
        assumptions_hash=str(payload["assumptions_hash"]),
        records_path=str(payload["records_path"]),
        records_content_hash=str(payload["records_content_hash"]),
        record_count=_as_int(payload["record_count"], "record_count"),
        symbol_order=tuple(str(item) for item in _require_list(payload, "symbol_order")),
        split_order=tuple(
            HistoricalSignalSplit(str(item))
            for item in _require_list(payload, "split_order")
        ),
        counts_by_symbol=tuple(
            (
                str(_require_mapping(item, "counts_by_symbol item")["symbol"]),
                _as_int(
                    _require_mapping(item, "counts_by_symbol item")["count"],
                    "symbol count",
                ),
            )
            for item in raw_symbol_counts
        ),
        counts_by_split=tuple(
            (
                HistoricalSignalSplit(
                    str(_require_mapping(item, "counts_by_split item")["split"])
                ),
                _as_int(
                    _require_mapping(item, "counts_by_split item")["count"],
                    "split count",
                ),
            )
            for item in raw_split_counts
        ),
    )


def persist_completed_historical_signal_campaign(
    *,
    records_path: Path,
    manifest_path: Path,
    records: Sequence[HistoricalSignalCampaignRecord],
    campaign_id: str,
    dataset_campaign_plan_id: str,
    dataset_campaign_execution_id: str,
    assumptions_hash: str,
    symbol_order: tuple[str, ...],
) -> HistoricalSignalCampaignManifest:
    """Persist records, reload them, then write and reload the completed manifest."""

    if records_path == manifest_path:
        raise ValueError("historical signal records and manifest paths must differ")
    _reject_existing_path(records_path)
    _reject_existing_path(manifest_path)
    created_records = False
    try:
        records_hash = write_historical_signal_records(
            records_path,
            records,
            symbol_order=symbol_order,
        )
        created_records = True
        reloaded = load_historical_signal_records(
            records_path,
            symbol_order=symbol_order,
            expected_content_hash=records_hash,
        )
        if tuple(record.to_payload() for record in reloaded) != tuple(
            record.to_payload() for record in records
        ):
            raise HistoricalSignalPersistenceError(
                "historical signal records changed during persistence round trip"
            )
        counts_by_symbol = tuple(
            (symbol, sum(record.symbol == symbol for record in reloaded))
            for symbol in symbol_order
        )
        split_order = (
            HistoricalSignalSplit.TRAIN,
            HistoricalSignalSplit.VALIDATION,
            HistoricalSignalSplit.FINAL_TEST,
        )
        counts_by_split = tuple(
            (split, sum(record.split is split for record in reloaded))
            for split in split_order
        )
        signal_campaign_id = derive_historical_signal_campaign_id(
            campaign_id=campaign_id,
            dataset_campaign_plan_id=dataset_campaign_plan_id,
            dataset_campaign_execution_id=dataset_campaign_execution_id,
            assumptions_hash=assumptions_hash,
            records_content_hash=records_hash,
        )
        manifest = HistoricalSignalCampaignManifest(
            signal_campaign_id=signal_campaign_id,
            campaign_id=campaign_id,
            dataset_campaign_plan_id=dataset_campaign_plan_id,
            dataset_campaign_execution_id=dataset_campaign_execution_id,
            assumptions_hash=assumptions_hash,
            records_path=str(records_path),
            records_content_hash=records_hash,
            record_count=len(reloaded),
            symbol_order=symbol_order,
            split_order=split_order,
            counts_by_symbol=counts_by_symbol,
            counts_by_split=counts_by_split,
        )
        write_historical_signal_campaign_manifest(manifest_path, manifest)
        loaded_manifest = load_historical_signal_campaign_manifest(manifest_path)
        if loaded_manifest != manifest:
            raise HistoricalSignalPersistenceError(
                "historical signal campaign manifest changed during round trip"
            )
        load_historical_signal_records(
            Path(loaded_manifest.records_path),
            symbol_order=loaded_manifest.symbol_order,
            expected_content_hash=loaded_manifest.records_content_hash,
        )
        return loaded_manifest
    except Exception:
        with suppress(FileNotFoundError):
            manifest_path.unlink()
        if created_records:
            with suppress(FileNotFoundError):
                records_path.unlink()
        raise


def hash_file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of exact persisted bytes."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_record(payload: Mapping[str, object]) -> HistoricalSignalCampaignRecord:
    raw_analysis = payload.get("analysis")
    if not isinstance(raw_analysis, dict):
        raise ValueError("historical signal analysis must be an object")
    source_datasets = tuple(
        _load_source_dataset(item)
        for item in _require_list(payload, "source_datasets")
    )
    return HistoricalSignalCampaignRecord(
        schema_version=_as_int(payload["schema_version"], "schema_version"),
        signal_record_id=str(payload["signal_record_id"]),
        campaign_id=str(payload["campaign_id"]),
        dataset_campaign_plan_id=str(payload["dataset_campaign_plan_id"]),
        dataset_campaign_execution_id=str(payload["dataset_campaign_execution_id"]),
        symbol=str(payload["symbol"]),
        timeframe=str(payload["timeframe"]),
        split=HistoricalSignalSplit(str(payload["split"])),
        decision_time=datetime.fromisoformat(str(payload["decision_time"])),
        parent_dataset_id=str(payload["parent_dataset_id"]),
        parent_dataset_hash=str(payload["parent_dataset_hash"]),
        source_dataset_id=str(payload["source_dataset_id"]),
        source_dataset_hash=str(payload["source_dataset_hash"]),
        source_datasets=source_datasets,
        assumptions_hash=str(payload["assumptions_hash"]),
        required_context_candles=_as_int(
            payload["required_context_candles"],
            "required_context_candles",
        ),
        accepted=_as_bool(payload["accepted"], "accepted"),
        unavailable_optional_data=tuple(
            str(item) for item in _require_list(payload, "unavailable_optional_data")
        ),
        failure_reason=_optional_string(payload.get("failure_reason")),
        analysis=raw_analysis,
    )


def _load_source_dataset(value: object) -> HistoricalSignalSourceDataset:
    payload = _require_mapping(value, "source_datasets item")
    return HistoricalSignalSourceDataset(
        timeframe=str(payload["timeframe"]),
        dataset_id=str(payload["dataset_id"]),
        content_hash=str(payload["content_hash"]),
    )


def _reject_existing_path(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"historical signal artifact already exists: {path}")


def _require_list(payload: Mapping[str, object], key: str) -> list[object]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"historical signal {key.replace('_', ' ')} must be a list")
    return value


def _require_mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"historical signal {name} must be an object")
    return value


def _as_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"historical signal {name} must be an integer")
    return value


def _as_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"historical signal {name} must be a boolean")
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("historical signal optional string must be text or null")
    return value
