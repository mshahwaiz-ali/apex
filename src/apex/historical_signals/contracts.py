"""Immutable contracts for reproducible historical futures signal campaigns."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from apex.backtesting.historical_signal_replay import HistoricalSignalSplit

HISTORICAL_SIGNAL_RECORD_SCHEMA_VERSION: Final = 2
HISTORICAL_SIGNAL_CAMPAIGN_SCHEMA_VERSION: Final = 1
_SPLIT_ORDER: Final = {
    HistoricalSignalSplit.TRAIN: 0,
    HistoricalSignalSplit.VALIDATION: 1,
    HistoricalSignalSplit.FINAL_TEST: 2,
}


@dataclass(frozen=True, slots=True)
class HistoricalSignalSourceDataset:
    """Exact persisted source binding for one replay timeframe."""

    timeframe: str
    dataset_id: str
    content_hash: str

    def __post_init__(self) -> None:
        if not self.timeframe.strip() or not self.dataset_id.strip():
            raise ValueError("historical signal source dataset fields cannot be empty")
        if not _is_sha256(self.content_hash):
            raise ValueError("historical signal source dataset hash must be SHA-256")

    def to_payload(self) -> dict[str, str]:
        """Return canonical persistence content."""

        return {
            "timeframe": self.timeframe,
            "dataset_id": self.dataset_id,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True, slots=True)
class HistoricalSignalCampaignRecord:
    """One immutable decision bound to exact frozen split datasets."""

    signal_record_id: str
    campaign_id: str
    dataset_campaign_plan_id: str
    dataset_campaign_execution_id: str
    symbol: str
    timeframe: str
    split: HistoricalSignalSplit
    decision_time: datetime
    parent_dataset_id: str
    parent_dataset_hash: str
    source_dataset_id: str
    source_dataset_hash: str
    source_datasets: tuple[HistoricalSignalSourceDataset, ...]
    assumptions_hash: str
    required_context_candles: int
    accepted: bool
    analysis: Mapping[str, object]
    unavailable_optional_data: tuple[str, ...] = ()
    failure_reason: str | None = None
    schema_version: int = HISTORICAL_SIGNAL_RECORD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "signal_record_id",
            "campaign_id",
            "dataset_campaign_plan_id",
            "dataset_campaign_execution_id",
            "symbol",
            "timeframe",
            "parent_dataset_id",
            "source_dataset_id",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"historical signal {name.replace('_', ' ')} cannot be empty")
        if self.decision_time.tzinfo is None or self.decision_time.utcoffset() is None:
            raise ValueError("historical signal decision time must be timezone-aware")
        for name in ("parent_dataset_hash", "source_dataset_hash", "assumptions_hash"):
            if not _is_sha256(str(getattr(self, name))):
                raise ValueError(
                    f"historical signal {name.replace('_', ' ')} must be a SHA-256 hex digest"
                )
        if self.required_context_candles < 1:
            raise ValueError("historical signal required context must be positive")
        if self.schema_version != HISTORICAL_SIGNAL_RECORD_SCHEMA_VERSION:
            raise ValueError("unsupported historical signal record schema version")
        if self.accepted and self.failure_reason is not None:
            raise ValueError("accepted historical signal cannot contain a failure reason")
        if tuple(sorted(set(self.unavailable_optional_data))) != self.unavailable_optional_data:
            raise ValueError(
                "historical signal unavailable optional data must be unique and sorted"
            )
        if not self.source_datasets:
            raise ValueError("historical signal source datasets cannot be empty")
        if tuple(item.timeframe for item in self.source_datasets) != tuple(
            sorted(item.timeframe for item in self.source_datasets)
        ):
            raise ValueError("historical signal source datasets must use timeframe order")
        if len({item.timeframe for item in self.source_datasets}) != len(self.source_datasets):
            raise ValueError("historical signal source datasets contain duplicate timeframes")
        if not any(
            item.dataset_id == self.source_dataset_id
            and item.content_hash == self.source_dataset_hash
            for item in self.source_datasets
        ):
            raise ValueError("historical signal primary source is not present in source datasets")
        expected_id = derive_historical_signal_record_id(
            campaign_id=self.campaign_id,
            symbol=self.symbol,
            split=self.split,
            decision_time=self.decision_time,
            source_dataset_hash=self.source_dataset_hash,
            assumptions_hash=self.assumptions_hash,
        )
        if self.signal_record_id != expected_id:
            raise ValueError("historical signal record ID does not match frozen identity")

    def to_payload(self) -> dict[str, object]:
        """Return canonical persistence content."""

        return {
            "schema_version": self.schema_version,
            "signal_record_id": self.signal_record_id,
            "campaign_id": self.campaign_id,
            "dataset_campaign_plan_id": self.dataset_campaign_plan_id,
            "dataset_campaign_execution_id": self.dataset_campaign_execution_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "split": self.split.value,
            "decision_time": self.decision_time.isoformat(),
            "parent_dataset_id": self.parent_dataset_id,
            "parent_dataset_hash": self.parent_dataset_hash,
            "source_dataset_id": self.source_dataset_id,
            "source_dataset_hash": self.source_dataset_hash,
            "source_datasets": [item.to_payload() for item in self.source_datasets],
            "assumptions_hash": self.assumptions_hash,
            "required_context_candles": self.required_context_candles,
            "accepted": self.accepted,
            "unavailable_optional_data": list(self.unavailable_optional_data),
            "failure_reason": self.failure_reason,
            "analysis": _canonicalize_mapping(self.analysis),
        }


@dataclass(frozen=True, slots=True)
class HistoricalSignalCampaignManifest:
    """Completed immutable signal-campaign manifest."""

    signal_campaign_id: str
    campaign_id: str
    dataset_campaign_plan_id: str
    dataset_campaign_execution_id: str
    assumptions_hash: str
    records_path: str
    records_content_hash: str
    record_count: int
    symbol_order: tuple[str, ...]
    split_order: tuple[HistoricalSignalSplit, ...]
    counts_by_symbol: tuple[tuple[str, int], ...]
    counts_by_split: tuple[tuple[HistoricalSignalSplit, int], ...]
    schema_version: int = HISTORICAL_SIGNAL_CAMPAIGN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "signal_campaign_id",
            "campaign_id",
            "dataset_campaign_plan_id",
            "dataset_campaign_execution_id",
            "records_path",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(
                    f"historical signal campaign {name.replace('_', ' ')} cannot be empty"
                )
        for name in ("assumptions_hash", "records_content_hash"):
            if not _is_sha256(str(getattr(self, name))):
                raise ValueError(
                    f"historical signal campaign {name.replace('_', ' ')} must be a SHA-256 hex digest"
                )
        if self.record_count < 1:
            raise ValueError("historical signal campaign must contain records")
        if not self.symbol_order or len(set(self.symbol_order)) != len(self.symbol_order):
            raise ValueError("historical signal campaign symbol order must be unique")
        expected_splits = (
            HistoricalSignalSplit.TRAIN,
            HistoricalSignalSplit.VALIDATION,
            HistoricalSignalSplit.FINAL_TEST,
        )
        if self.split_order != expected_splits:
            raise ValueError("historical signal campaign split order is invalid")
        if tuple(symbol for symbol, _ in self.counts_by_symbol) != self.symbol_order:
            raise ValueError("historical signal symbol counts must follow frozen symbol order")
        if tuple(split for split, _ in self.counts_by_split) != self.split_order:
            raise ValueError("historical signal split counts must follow explicit split order")
        if any(count < 0 for _, count in self.counts_by_symbol):
            raise ValueError("historical signal symbol counts cannot be negative")
        if any(count < 0 for _, count in self.counts_by_split):
            raise ValueError("historical signal split counts cannot be negative")
        if sum(count for _, count in self.counts_by_symbol) != self.record_count:
            raise ValueError("historical signal symbol counts do not match record count")
        if sum(count for _, count in self.counts_by_split) != self.record_count:
            raise ValueError("historical signal split counts do not match record count")
        if self.schema_version != HISTORICAL_SIGNAL_CAMPAIGN_SCHEMA_VERSION:
            raise ValueError("unsupported historical signal campaign schema version")
        expected_id = derive_historical_signal_campaign_id(
            campaign_id=self.campaign_id,
            dataset_campaign_plan_id=self.dataset_campaign_plan_id,
            dataset_campaign_execution_id=self.dataset_campaign_execution_id,
            assumptions_hash=self.assumptions_hash,
            records_content_hash=self.records_content_hash,
        )
        if self.signal_campaign_id != expected_id:
            raise ValueError("historical signal campaign ID does not match frozen identity")

    def to_payload(self) -> dict[str, object]:
        """Return canonical JSON manifest content."""

        return {
            "schema_version": self.schema_version,
            "signal_campaign_id": self.signal_campaign_id,
            "campaign_id": self.campaign_id,
            "dataset_campaign_plan_id": self.dataset_campaign_plan_id,
            "dataset_campaign_execution_id": self.dataset_campaign_execution_id,
            "assumptions_hash": self.assumptions_hash,
            "records_path": self.records_path,
            "records_content_hash": self.records_content_hash,
            "record_count": self.record_count,
            "symbol_order": list(self.symbol_order),
            "split_order": [split.value for split in self.split_order],
            "counts_by_symbol": [
                {"symbol": symbol, "count": count}
                for symbol, count in self.counts_by_symbol
            ],
            "counts_by_split": [
                {"split": split.value, "count": count}
                for split, count in self.counts_by_split
            ],
        }


def derive_historical_signal_record_id(
    *,
    campaign_id: str,
    symbol: str,
    split: HistoricalSignalSplit,
    decision_time: datetime,
    source_dataset_hash: str,
    assumptions_hash: str,
) -> str:
    """Derive the stable record identity from frozen decision inputs."""

    if decision_time.tzinfo is None or decision_time.utcoffset() is None:
        raise ValueError("historical signal decision time must be timezone-aware")
    identity = {
        "campaign_id": campaign_id.strip(),
        "symbol": symbol.strip().upper(),
        "split": split.value,
        "decision_time": decision_time.isoformat(),
        "source_dataset_hash": source_dataset_hash,
        "assumptions_hash": assumptions_hash,
    }
    return f"historical-signal-{_hash_payload(identity)}"


def derive_historical_signal_campaign_id(
    *,
    campaign_id: str,
    dataset_campaign_plan_id: str,
    dataset_campaign_execution_id: str,
    assumptions_hash: str,
    records_content_hash: str,
) -> str:
    """Derive one stable completed-campaign identity."""

    identity = {
        "campaign_id": campaign_id.strip(),
        "dataset_campaign_plan_id": dataset_campaign_plan_id.strip(),
        "dataset_campaign_execution_id": dataset_campaign_execution_id.strip(),
        "assumptions_hash": assumptions_hash,
        "records_content_hash": records_content_hash,
    }
    return f"historical-signal-campaign-{_hash_payload(identity)}"


def validate_historical_signal_record_sequence(
    records: Sequence[HistoricalSignalCampaignRecord],
    *,
    symbol_order: tuple[str, ...],
) -> None:
    """Reject duplicates and enforce symbol, split, then chronological order."""

    if not records:
        raise ValueError("historical signal campaign produced no records")
    if not symbol_order or len(set(symbol_order)) != len(symbol_order):
        raise ValueError("historical signal symbol order must be non-empty and unique")
    symbol_indexes = {symbol: index for index, symbol in enumerate(symbol_order)}
    identities = tuple(record.signal_record_id for record in records)
    if len(set(identities)) != len(identities):
        raise ValueError("historical signal campaign contains duplicate signal identities")
    unknown = tuple(record.symbol for record in records if record.symbol not in symbol_indexes)
    if unknown:
        raise ValueError(f"historical signal record has unexpected symbol: {unknown[0]}")
    order_keys = tuple(
        (
            symbol_indexes[record.symbol],
            _SPLIT_ORDER[record.split],
            record.decision_time,
            record.signal_record_id,
        )
        for record in records
    )
    if order_keys != tuple(sorted(order_keys)):
        raise ValueError(
            "historical signal records must follow frozen symbol, split, and chronological order"
        )


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


def _hash_payload(payload: Mapping[str, object]) -> str:
    serialized = json.dumps(
        _canonicalize_mapping(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
